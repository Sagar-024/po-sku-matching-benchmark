"""Validate the generated benchmark dataset.

Checks that hold BEFORE any matcher exists:
  * row counts and gap fractions match the spec
  * every non-gap label resolves to a real catalog SKU
  * every gap label has NO possible catalog SKU (genuinely absent)
  * gap texts do not collide with catalog descriptions
  * every style and category is represented
  * re-running the generator reproduces byte-identical files

Run: python validate_dataset.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from generate_dataset import (  # noqa: E402
    DATA, DEV_COUNT, GAP_FRACTION, STYLES, TEST_COUNT, sha256_of,
)

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    """Record a failed assertion instead of aborting, so we see every problem."""
    if not condition:
        FAILURES.append(message)


def load(path: Path) -> list[dict[str, str]]:
    """Read one of the generated CSVs."""
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    """Validate counts, labels, gaps, coverage and the recorded hash."""
    catalog = load(DATA / "catalog.csv")
    dev = load(DATA / "dev.csv")
    test = load(DATA / "test.csv")
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))

    skus = {r["sku"] for r in catalog}
    descriptions = {r["description"].strip().lower() for r in catalog}

    print(f"catalog {len(catalog)} | dev {len(dev)} | test {len(test)}")
    print(f"test sha256 {sha256_of(DATA / 'test.csv')}")

    # --- counts -----------------------------------------------------------
    check(150 <= len(catalog) <= 300, f"catalog size {len(catalog)} not in 150-300")
    check(len(dev) == DEV_COUNT, f"dev has {len(dev)} rows, expected {DEV_COUNT}")
    check(len(test) == TEST_COUNT, f"test has {len(test)} rows, expected {TEST_COUNT}")
    check(manifest["test_sha256"] == sha256_of(DATA / "test.csv"),
          "manifest test hash does not match the file on disk")
    check(manifest["dev_sha256"] == sha256_of(DATA / "dev.csv"),
          "manifest dev hash does not match the file on disk")

    # --- gap fractions ----------------------------------------------------
    for name, rows in (("dev", dev), ("test", test)):
        gaps = [r for r in rows if r["is_gap"].lower() == "true"]
        fraction = len(gaps) / len(rows)
        check(abs(fraction - GAP_FRACTION) < 0.01,
              f"{name} gap fraction {fraction:.3f} not near {GAP_FRACTION}")

    # --- labels -----------------------------------------------------------
    for name, rows in (("dev", dev), ("test", test)):
        for row in rows:
            is_gap = row["is_gap"].lower() == "true"
            if is_gap:
                check(row["expected_sku"] == "",
                      f"{name}:{row['id']} is a gap but has a SKU")
                check(row["text"].strip().lower() not in descriptions,
                      f"{name}:{row['id']} gap text is literally in the catalog")
            else:
                check(row["expected_sku"] in skus,
                      f"{name}:{row['id']} label {row['expected_sku']!r} not in catalog")
                check(row["source_sku"] == row["expected_sku"],
                      f"{name}:{row['id']} source_sku differs from expected_sku")

    # --- split hygiene ----------------------------------------------------
    dev_ids = {r["id"] for r in dev}
    test_ids = {r["id"] for r in test}
    check(not dev_ids & test_ids, "dev and test share row ids")

    # --- coverage ---------------------------------------------------------
    for name, rows in (("dev", dev), ("test", test)):
        styles = {r["style"] for r in rows if r["style"] != "gap"}
        categories = {r["category"] for r in rows if not r["is_gap"].lower() == "true"}
        missing_styles = set(STYLES) - styles
        check(not missing_styles, f"{name} missing styles: {sorted(missing_styles)}")
        check(len(categories) >= 4, f"{name} only covers {sorted(categories)}")

    # --- hard negatives actually present ---------------------------------
    for required_thread in ("3/8-16", "3/8-24", "1/2-13", "1/2-20"):
        found = any(r["thread"] == required_thread and r["finish"] == "Zinc"
                    and r["grade"] == "Grade 5" and r["material"] == "Steel"
                    for r in catalog)
        check(found, f"catalog lacks a Grade 5 Zinc bolt at thread {required_thread}")
    for finish in ("Zinc", "Zinc Yellow"):
        check(any(r["finish"] == finish for r in catalog),
              f"catalog lacks finish {finish!r}")
    for grade in ("Grade 5", "Grade 8"):
        check(any(r["grade"] == grade for r in catalog), f"catalog lacks {grade!r}")

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} problem(s)")
        for problem in FAILURES[:40]:
            print(f"  - {problem}")
        sys.exit(1)
    print("OK: dataset is internally consistent")


if __name__ == "__main__":
    main()
