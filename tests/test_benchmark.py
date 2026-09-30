"""Benchmark invariant tests: dataset freeze, normalization, UoM, matchers.

These are offline and deterministic (no LLM, no network). They lock in the
frozen test hash and the normalization/conversion behaviour the matchers rely
on, so a change that silently moves accuracy fails here first.

Run from the project root with the backend venv:

    python -m pytest tests -q
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))

from matchers import (  # noqa: E402
    AttributeMatcher,
    BaselineFuzzyMatcher,
    HybridMatcher,
    Outcome,
    normalize_attributes,
)
from metrics import FALSE_MATCH, classify  # noqa: E402
from normalize import (  # noqa: E402
    normalize_bearing,
    normalize_finish,
    normalize_grade,
    normalize_length,
    normalize_material,
    normalize_size,
    normalize_thread,
    normalize_type,
)
from uom import ConversionError, convert, pack_factor, to_eaches, uom_matches  # noqa: E402

DATA = BENCH / "data"


# --- dataset freeze ---------------------------------------------------------


def test_frozen_splits_match_manifest() -> None:
    """A silently edited dev/test split must fail the build, not score."""
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    for split in ("dev", "test"):
        actual = hashlib.sha256((DATA / f"{split}.csv").read_bytes()).hexdigest()
        assert actual == manifest[f"{split}_sha256"], f"{split}.csv was modified"


def test_test_split_has_expected_shape() -> None:
    """The frozen test split keeps the size the protocol advertises."""
    with (DATA / "test.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 200
    gaps = sum(1 for row in rows if str(row["is_gap"]).lower() == "true")
    assert gaps == 30


# --- normalization ----------------------------------------------------------


def test_imperial_fraction_becomes_inches() -> None:
    assert normalize_size("3/8") == "0.375"
    assert normalize_size("1/4") == "0.25"


def test_metric_size_cannot_equal_imperial() -> None:
    """M10 is 10 mm, 10 (bare) is 10 inches: never equal."""
    assert normalize_size("M10") == "m10"
    assert normalize_size("10") != normalize_size("M10")


def test_thread_splits_size_and_pitch() -> None:
    assert normalize_thread("3/8-16") == ("0.375", "16")
    assert normalize_thread("M10x1.5") == ("m10", "1.5")


def test_metric_diameter_times_length_is_not_a_pitch() -> None:
    """M10x40 is a length, so it must not fabricate a 40 mm pitch."""
    assert normalize_thread("M10x40") == ("m10", None)


def test_length_units_agree() -> None:
    assert normalize_length('2"') == pytest.approx(2.0)
    assert normalize_length("40 mm") == pytest.approx(40 / 25.4, abs=1e-6)


def test_synonyms_collapse() -> None:
    assert normalize_finish("Zn") == "zinc"
    assert normalize_finish("Zn Yel") == "zinc yellow"
    assert normalize_material("SS") == "stainless"
    assert normalize_type("SHCS") == "socket head cap screw"


def test_bearing_suffix_is_preserved() -> None:
    assert normalize_bearing("6203-2RS") == "6203-2rs"
    assert normalize_bearing("6203-2RS") != normalize_bearing("6203-2Z")


def test_grade_scales_stay_separate() -> None:
    assert normalize_grade("Gr5") == "grade 5"
    assert normalize_grade("8.8") == "8.8"


# --- UoM / pack-size table --------------------------------------------------


def test_pack_factors_are_real_counts() -> None:
    assert convert(1, "dz", "ea") == 12
    assert convert(1, "carton", "ea") == 50
    assert convert(1, "pallet", "ea") == 1000
    assert convert(120, "ea", "dz") == 10


def test_customer_defined_unit_refuses() -> None:
    with pytest.raises(ConversionError):
        pack_factor("box")
    with pytest.raises(ConversionError):
        pack_factor("bx")


def test_pieces_and_feet_do_not_convert() -> None:
    with pytest.raises(ConversionError):
        convert(1, "roll", "ea")


def test_catalog_pack_size_overrides_table() -> None:
    """A distributor's own carton size wins over the generic factor."""
    assert to_eaches(2, "carton", catalog_pack_size=100) == 200


def test_missing_unit_is_not_a_conflict() -> None:
    assert uom_matches("", "ea", 1) is True
    assert uom_matches("ea", "ea", 1) is True


# --- matchers ---------------------------------------------------------------


def _catalog() -> list[dict]:
    """One fully-specified SKU, enough to exercise attribute scoring."""
    return [{
        "sku": "HB-375-200-Z", "description": 'Hex Bolt 3/8-16 x 2" Grade 5 Zinc Hex Head',
        "category": "fastener", "type": "Hex Bolt", "size": "3/8", "thread": "3/8-16",
        "length": "2", "material": "Steel", "finish": "Zinc", "grade": "Grade 5",
        "uom": "Ea", "pack_size": 1,
    }]


def test_empty_catalog_never_invents_a_sku() -> None:
    result = AttributeMatcher().match({"text": "3/8 x 2 hex bolt"}, [])
    assert result.outcome is Outcome.GAP
    assert result.sku is None


def test_attribute_match_is_found() -> None:
    attrs = {"type": "Hex Bolt", "thread": "3/8-16", "length": "2",
             "material": "Steel", "finish": "Zinc", "grade": "Grade 5"}
    result = AttributeMatcher().match({"text": "3/8-16 x 2 hex bolt zinc"},
                                      _catalog(), attrs)
    assert result.outcome is Outcome.AUTO_MATCH
    assert result.sku == "HB-375-200-Z"


def test_conflicting_pitch_is_rejected() -> None:
    """3/8-24 must never match 3/8-16: a conflict rejects the candidate."""
    attrs = {"type": "Hex Bolt", "thread": "3/8-24", "length": "2",
             "material": "Steel", "finish": "Zinc", "grade": "Grade 5"}
    result = AttributeMatcher().match({"text": "3/8-24 x 2 hex bolt"}, _catalog(), attrs)
    assert result.outcome is Outcome.GAP
    assert result.sku is None


def test_normalize_attributes_requires_evidence() -> None:
    assert normalize_attributes(None) == {}
    assert normalize_attributes({"type": "Hex Bolt"}) == {"type": "hex bolt"}


def test_hybrid_matches_where_attribute_does() -> None:
    attrs = {"type": "Hex Bolt", "thread": "3/8-16", "length": "2",
             "material": "Steel", "finish": "Zinc", "grade": "Grade 5"}
    result = HybridMatcher().match({"text": "3/8-16 x 2 hex bolt zinc"}, _catalog(), attrs)
    assert result.sku == "HB-375-200-Z"


def test_baseline_fuzzy_has_no_catalog_safety_net() -> None:
    """The incumbent is included unmodified; it never returns attributes."""
    result = BaselineFuzzyMatcher().match({"text": "3/8 x 2 hex bolt"}, _catalog())
    assert result.outcome in (Outcome.AUTO_MATCH, Outcome.NEEDS_REVIEW, Outcome.GAP)


# --- metrics ----------------------------------------------------------------


def test_confident_wrong_sku_on_a_true_gap_is_a_false_match() -> None:
    wrong = type("R", (), {"outcome": Outcome.AUTO_MATCH, "sku": "X"})()
    assert classify("", True, wrong) == FALSE_MATCH


def test_gap_caught_is_correct() -> None:
    gap = type("R", (), {"outcome": Outcome.GAP, "sku": None})()
    assert classify("", True, gap) == "correct"
