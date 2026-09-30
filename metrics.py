"""Metrics for the frozen test set.

Definitions are chosen so the DANGEROUS error cannot be hidden:

  false match   AUTO_MATCH with a wrong SKU. That error writes a wrong part
                into an ERP, so it is reported both as a share of all rows and
                as a share of the rows it chose to auto-match.

Nothing here reads a matcher's confidence to decide correctness.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from matchers import MatchResult, Outcome

CORRECT = "correct"
FALSE_MATCH = "false_match"
MISSED = "missed"
FALSE_GAP = "false_gap"


@dataclass
class RowOutcome:
    """One scored row, keeping enough detail to explain any failure."""

    row_id: str
    text: str
    expected_sku: str
    is_gap: bool
    category: str
    style: str
    outcome: Outcome
    predicted_sku: str | None
    confidence: float
    reason: str
    verdict: str


@dataclass
class Metrics:
    """Aggregate metrics plus the per-row detail behind them."""

    matcher: str
    total: int = 0
    correct: int = 0
    false_match: int = 0
    missed: int = 0
    false_gap: int = 0
    auto: int = 0
    review: int = 0
    gap: int = 0
    true_gaps: int = 0
    gaps_caught: int = 0
    rows: list[RowOutcome] = field(default_factory=list)
    by_style: dict = field(default_factory=lambda: defaultdict(dict))
    by_category: dict = field(default_factory=lambda: defaultdict(dict))

    @property
    def top1_accuracy(self) -> float:
        """Share of rows the matcher got completely right."""
        return self.correct / self.total if self.total else 0.0

    @property
    def false_match_rate(self) -> float:
        """Confidently wrong as a share of ALL rows. The headline safety number."""
        return self.false_match / self.total if self.total else 0.0

    @property
    def false_match_share_of_auto(self) -> float:
        """Confidently wrong as a share of rows it chose to auto-match."""
        return self.false_match / self.auto if self.auto else 0.0

    @property
    def gap_recall(self) -> float:
        """Share of real catalog gaps correctly flagged as gaps."""
        return self.gaps_caught / self.true_gaps if self.true_gaps else 0.0

    @property
    def gap_precision(self) -> float:
        """Share of GAP verdicts that were genuinely gaps."""
        return self.gaps_caught / self.gap if self.gap else 0.0

    @property
    def review_rate(self) -> float:
        """Share of rows pushed to a human."""
        return self.review / self.total if self.total else 0.0

    @property
    def auto_rate(self) -> float:
        """Share of rows handled without a human."""
        return self.auto / self.total if self.total else 0.0


def classify(expected_sku: str, is_gap: bool, result: MatchResult) -> str:
    """
    Map one verdict onto the correctness classes.

    A confident wrong SKU is always FALSE_MATCH, including when a true gap was
    force-matched into the catalog.
    """
    if is_gap:
        return CORRECT if result.outcome is Outcome.GAP else FALSE_MATCH
    if result.outcome is Outcome.GAP:
        return MISSED
    if result.sku == expected_sku:
        return CORRECT
    if result.outcome is Outcome.AUTO_MATCH:
        return FALSE_MATCH
    # Right to be unsure, but it still named the wrong part.
    return FALSE_GAP



def score(matcher_name: str, rows: list[dict],
          results: list[MatchResult]) -> Metrics:
    """Aggregate per-row verdicts into the full metric set."""
    metrics = Metrics(matcher=matcher_name)
    for row, result in zip(rows, results, strict=True):
        is_gap = str(row["is_gap"]).lower() == "true"
        expected = row["expected_sku"]
        verdict = classify(expected, is_gap, result)

        metrics.total += 1
        metrics.rows.append(RowOutcome(
            row_id=row["id"], text=row["text"], expected_sku=expected,
            is_gap=is_gap, category=row["category"], style=row["style"],
            outcome=result.outcome, predicted_sku=result.sku,
            confidence=result.confidence, reason=result.reason, verdict=verdict,
        ))
        setattr(metrics, verdict, getattr(metrics, verdict) + 1)
        if result.outcome is Outcome.AUTO_MATCH:
            metrics.auto += 1
        elif result.outcome is Outcome.NEEDS_REVIEW:
            metrics.review += 1
        else:
            metrics.gap += 1
        if is_gap:
            metrics.true_gaps += 1
            if result.outcome is Outcome.GAP:
                metrics.gaps_caught += 1

        for key, bucket in (("style", metrics.by_style),
                            ("category", metrics.by_category)):
            name = row[key] if row[key] else ("gap" if is_gap else "unknown")
            entry = bucket[name]
            entry["total"] = entry.get("total", 0) + 1
            entry["correct"] = entry.get("correct", 0) + (verdict == CORRECT)
            entry["false_match"] = entry.get("false_match", 0) + (verdict == FALSE_MATCH)
    return metrics


def uom_accuracy(rows: list[dict],
                 catalog_by_sku: dict[str, dict]) -> tuple[float, int]:
    """
    Measure pack-size conversion only on rows that carry a PO unit.

    Reported separately from matching: a correct SKU with the wrong pack size
    still ships the wrong quantity.
    """
    from uom import ConversionError, to_eaches

    checked = correct = 0
    for row in rows:
        if not row.get("po_uom"):
            continue
        checked += 1
        expected = float(row.get("expected_base_qty") or 0)
        catalog_row = catalog_by_sku.get(row.get("expected_sku", ""), {})
        pack = int(catalog_row.get("pack_size") or 1)
        try:
            actual = to_eaches(float(row.get("po_quantity") or 0),
                               row["po_uom"], pack)
        except ConversionError:
            continue
        if abs(actual - expected) < 1e-6:
            correct += 1
    return (correct / checked if checked else 0.0), checked


def format_table(all_metrics: list[Metrics]) -> str:
    """Render the A/B/C comparison table for the console and the README."""
    header = (f"{'matcher':<20}{'top-1':>8}{'false-match':>13}{'gap-rec':>9}"
              f"{'gap-prec':>10}{'review':>8}{'auto':>7}")
    lines = [header, "-" * len(header)]
    for metrics in all_metrics:
        lines.append(
            f"{metrics.matcher:<20}"
            f"{metrics.top1_accuracy * 100:>7.1f}%"
            f"{metrics.false_match_rate * 100:>12.1f}%"
            f"{metrics.gap_recall * 100:>8.1f}%"
            f"{metrics.gap_precision * 100:>9.1f}%"
            f"{metrics.review_rate * 100:>7.1f}%"
            f"{metrics.auto_rate * 100:>6.1f}%"
        )
    return "\n".join(lines)


def format_breakdown(metrics: Metrics, key: str) -> str:
    """Per-style or per-category accuracy for one matcher."""
    bucket = metrics.by_style if key == "style" else metrics.by_category
    lines = [f"{key:<18}{'n':>4}{'correct':>9}{'false-match':>13}"]
    for name in sorted(bucket):
        entry = bucket[name]
        total = entry.get("total", 0) or 1
        lines.append(
            f"{name:<18}{entry.get('total', 0):>4}"
            f"{entry.get('correct', 0) / total * 100:>8.1f}%"
            f"{entry.get('false_match', 0) / total * 100:>12.1f}%"
        )
    return "\n".join(lines)
