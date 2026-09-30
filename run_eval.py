"""Run the A/B/C comparison on a frozen split and report every failure.

Verifies the test hash against the manifest before scoring, so a silently
edited test set cannot produce a flattering number.

Usage:
    python run_eval.py --split dev
    python run_eval.py --split test
    python run_eval.py --split test --no-llm
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

BENCH = Path(__file__).parent
sys.path.insert(0, str(BENCH))

from llm_extract import extract_all, read_usage, reset_usage  # noqa: E402
from matchers import build_matchers  # noqa: E402
from metrics import (  # noqa: E402
    FALSE_GAP,
    FALSE_MATCH,
    MISSED,
    format_breakdown,
    format_table,
    score,
    uom_accuracy,
)

DATA = BENCH / "data"
RESULTS_DIR = BENCH / "results"


def load_csv(path: Path) -> list[dict[str, str]]:
    """Read one generated CSV."""
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def verify_split(split: str) -> None:
    """Refuse to score a test split whose hash no longer matches the manifest."""
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    path = DATA / f"{split}.csv"
    actual = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
    expected = manifest.get(f"{split}_sha256")
    if expected and actual != expected:
        raise SystemExit(
            f"{split}.csv hash mismatch.\n  expected {expected}\n  actual   {actual}\n"
            "The frozen split was modified. Re-freeze and report BOTH runs."
        )
    print(f"{split}.csv verified against manifest ({actual[:16]}...)")


def main() -> None:
    """Score every matcher and write the comparison plus failure analysis."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), default="test")
    parser.add_argument("--no-llm", action="store_true",
                        help="use the rule-based fallback extractor instead of the model")
    args = parser.parse_args()

    verify_split(args.split)
    catalog = load_csv(DATA / "catalog.csv")
    rows = load_csv(DATA / f"{args.split}.csv")
    catalog_by_sku = {row["sku"]: row for row in catalog}

    if args.split == "test":
        reset_usage()
    else:
        # Dev reruns accumulate cache hits; start the log fresh each time so
        # the reported numbers describe exactly this invocation.
        reset_usage()
    texts = [row["text"] for row in rows]
    attributes, usage = extract_all(texts, use_llm=not args.no_llm)

    print(f"\nsplit={args.split}  rows={len(rows)}  catalog={len(catalog)}")
    print(f"extraction: llm_calls={usage['llm_calls']} "
          f"cache_hits={usage['cache_hits']} fallbacks={usage['fallbacks']} "
          f"tokens={usage['total_tokens']} seconds={usage.get('seconds', 0)}")
    if usage["fallbacks"]:
        print(f"\n!! WARNING: {usage['fallbacks']} batch(es) fell back to the rule "
              f"extractor.\n!! Matcher B/C results below are NOT LLM-quality. "
              f"Check cache/usage.jsonl for the reason.\n")

    all_metrics = []
    for matcher in build_matchers():
        results = [
            matcher.match(row, catalog, attr)
            for row, attr in zip(rows, attributes, strict=True)
        ]
        all_metrics.append(score(matcher.name, rows, results))

    print(format_table(all_metrics))

    uom_rate, uom_checked = uom_accuracy(rows, catalog_by_sku)
    print(f"\nUoM conversion accuracy: {uom_rate * 100:.1f}% on {uom_checked} rows "
          f"with a stated pack unit")

    for metrics in all_metrics:
        print(f"\n--- {metrics.matcher}: by style ---")
        print(format_breakdown(metrics, "style"))

    best = max(all_metrics, key=lambda m: (m.top1_accuracy, -m.false_match_rate))
    print(f"\n=== best matcher: {best.matcher} "
          f"(top-1 {best.top1_accuracy * 100:.1f}%, "
          f"false-match {best.false_match_rate * 100:.1f}%) ===")

    RESULTS_DIR.mkdir(exist_ok=True)
    write_results(args.split, all_metrics, best, usage, uom_rate, uom_checked)


def _cause(row) -> str:
    """Bucket a failure by its mechanism, so the list is diagnosable."""
    if row.verdict == FALSE_MATCH:
        if row.is_gap:
            return "true gap force-matched into the catalog"
        return f"wrong SKU auto-matched (expected {row.expected_sku}, got {row.predicted_sku})"
    if row.verdict == MISSED:
        return "catalog item reported as a gap (matcher gave up)"
    if row.verdict == FALSE_GAP:
        return f"sent to review with the wrong SKU ({row.predicted_sku})"
    return "other"


def write_results(split: str, all_metrics: list, best, usage: dict,
                  uom_rate: float, uom_checked: int) -> None:
    """Write per-row results, a summary, and the full failure list."""
    for metrics in all_metrics:
        path = RESULTS_DIR / f"{split}_{metrics.matcher}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "text", "expected_sku", "is_gap", "style",
                             "category", "outcome", "predicted_sku",
                             "confidence", "reason", "verdict"])
            for row in metrics.rows:
                writer.writerow([row.row_id, row.text, row.expected_sku,
                                 row.is_gap, row.style, row.category,
                                 row.outcome.value, row.predicted_sku or "",
                                 f"{row.confidence:.3f}", row.reason, row.verdict])

    summary = {
        "split": split,
        "frozen_test_sha256": json.loads(
            (DATA / "manifest.json").read_text(encoding="utf-8")
        ).get(f"{split}_sha256"),
        "usage": usage,
        "uom_accuracy": round(uom_rate, 4),
        "uom_rows_checked": uom_checked,
        "best_matcher": best.matcher,
        "matchers": [
            {
                "name": m.matcher,
                "top1_accuracy": round(m.top1_accuracy, 4),
                "false_match_rate": round(m.false_match_rate, 4),
                "false_match_share_of_auto": round(m.false_match_share_of_auto, 4),
                "gap_recall": round(m.gap_recall, 4),
                "gap_precision": round(m.gap_precision, 4),
                "review_rate": round(m.review_rate, 4),
                "auto_rate": round(m.auto_rate, 4),
                "counts": {
                    "total": m.total, "correct": m.correct,
                    "false_match": m.false_match, "missed": m.missed,
                    "false_gap": m.false_gap,
                },
            }
            for m in all_metrics
        ],
    }
    (RESULTS_DIR / f"{split}_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    # Every failure of the best matcher, grouped by cause. None are dropped.
    failures = [r for r in best.rows if r.verdict != "correct"]
    groups: dict[str, list] = {}
    for row in failures:
        groups.setdefault(_cause(row), []).append(row)

    lines = [
        f"# Failure analysis — {best.matcher} on `{split}`",
        "",
        f"Split: `{split}` | rows: {best.total} | failures: **{len(failures)}**",
        "",
        "Every failure is listed. Nothing is filtered or dropped.",
        "ALL DATA IS SYNTHETIC.",
        "",
        "## By cause",
        "",
        f"| cause | count | share of failures |",
        f"|---|---|---|",
    ]
    for cause, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        share = len(items) / len(failures) * 100 if failures else 0
        lines.append(f"| {cause} | {len(items)} | {share:.1f}% |")
    lines.append("")

    for cause, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"## {cause} ({len(items)})")
        lines.append("")
        lines.append("| id | style | text | expected | predicted | reason |")
        lines.append("|---|---|---|---|---|---|")
        for row in items:
            text = row.text.replace("|", "\\|")
            lines.append(
                f"| {row.row_id} | {row.style} | `{text}` | "
                f"{row.expected_sku or '(gap)'} | {row.predicted_sku or '—'} | "
                f"{row.reason} |"
            )
        lines.append("")

    (RESULTS_DIR / f"{split}_failures.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(f"\nwrote {RESULTS_DIR}/{split}_summary.json")
    print(f"wrote {RESULTS_DIR}/{split}_failures.md")


if __name__ == "__main__":
    main()
