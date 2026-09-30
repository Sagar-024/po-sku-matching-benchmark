"""Three matchers behind one interface, so results are directly comparable.

    A  baseline  -- rapidfuzz token_sort_ratio, the existing production matcher
    B  attribute -- LLM-extracted + deterministically normalized attributes
    C  hybrid    -- B decides, fuzzy only breaks ties among B's survivors

Every matcher returns the same tri-state result:

    AUTO_MATCH    confident, safe to write straight into the ERP
    NEEDS_REVIEW  a human should look; a wrong auto-match costs more than a
                  review, so ambiguity resolves to review, never to a guess
    GAP           nothing in the catalog is close enough

Thresholds live here and are tuned on dev.csv only. test.csv is never used to
choose them.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol, Sequence

BENCH = Path(__file__).parent
sys.path.insert(0, str(BENCH))

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

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None


class Outcome(str, Enum):
    """The three verdicts every matcher must produce."""

    AUTO_MATCH = "AUTO_MATCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    GAP = "GAP"


@dataclass
class MatchResult:
    """One matcher's verdict for one PO line."""

    outcome: Outcome
    sku: str | None = None
    confidence: float = 0.0
    reason: str = ""


class Matcher(Protocol):
    """Common interface so run_eval can treat all matchers identically."""

    name: str

    def match(self, row: dict, catalog: Sequence[dict],
              attributes: dict | None = None) -> MatchResult:
        """Return a verdict for one labeled row."""
        ...


# --- attribute normalization ------------------------------------------------

# Attributes that identify WHICH product it is. A conflict here means a
# different part, so the candidate is rejected outright. thread_pitch is
# compared only when BOTH sides state it: "M12" is compatible with "M12-1.75"
# (underspecified), while "3/8-16" vs "3/8-24" is a genuine conflict.
DISCRIMINATING = ("type", "size", "thread_size", "thread_pitch", "bearing",
                  "length", "material", "finish", "grade")

WEIGHTS = {
    "bearing": 45.0,
    "type": 30.0,
    "thread_size": 25.0,
    "thread_pitch": 15.0,
    "size": 25.0,
    "length": 20.0,
    "material": 10.0,
    "finish": 10.0,
    "grade": 10.0,
}

# Tuned on dev.csv only.
AUTO_THRESHOLD = 55.0
REVIEW_THRESHOLD = 25.0
AMBIGUITY_MARGIN = 6.0

# Bearing designation embedded in a catalog description, e.g. "6203-2RS".
_BEARING_IN_TEXT = re.compile(r"\b(\d{4})\s*-\s*([0-9A-Za-z]{2,3})\b")



def normalize_attributes(raw: dict | None) -> dict[str, str]:
    """
    Canonicalize raw LLM-extracted attributes into comparable strings.

    This is the deterministic half of matcher B: the model reports what the
    text said, this function decides what that means.
    """
    if not raw:
        return {}
    out: dict[str, str] = {}

    product_type = normalize_type(raw.get("type") or "")
    if product_type:
        out["type"] = product_type

    thread_size, thread_pitch = normalize_thread(raw.get("thread") or "")
    if thread_size:
        out["thread_size"] = thread_size
        if thread_pitch:
            out["thread_pitch"] = thread_pitch
        # A bare size is the same statement about the thread's diameter.
        if "size" not in out:
            out["size"] = thread_size
    else:
        size = normalize_size(raw.get("size") or "")
        if size:
            out["size"] = size

    length = normalize_length(raw.get("length") or "")
    if length is not None:
        out["length"] = f"{length:g}"

    material = normalize_material(raw.get("material") or "")
    if material:
        out["material"] = material

    finish = normalize_finish(raw.get("finish") or "")
    if finish:
        out["finish"] = finish

    grade = normalize_grade(raw.get("grade") or "", material)
    if grade:
        out["grade"] = grade

    if raw.get("bearing"):
        bearing = normalize_bearing(raw["bearing"])
        if bearing:
            out["bearing"] = bearing

    return out


def catalog_attributes(row: dict) -> dict[str, str]:
    """
    Build canonical attributes for one catalog row from its own columns.

    The catalog is already structured, so no model call is needed or wanted:
    the customer's own attributes are the source of truth.
    """
    out: dict[str, str] = {}
    if row.get("type"):
        normalized = normalize_type(row["type"])
        if normalized:
            out["type"] = normalized

    thread_size, thread_pitch = normalize_thread(row.get("thread") or "")
    if thread_size:
        out["thread_size"] = thread_size
        if thread_pitch:
            out["thread_pitch"] = thread_pitch
        if "size" not in out:
            out["size"] = thread_size
    elif row.get("size"):
        size = normalize_size(row["size"])
        if size:
            out["size"] = size

    if row.get("length"):
        length = normalize_length(row["length"])
        if length is not None:
            out["length"] = f"{length:g}"

    if row.get("material"):
        material = normalize_material(row["material"])
        if material:
            out["material"] = material

    if row.get("finish"):
        finish = normalize_finish(row["finish"])
        if finish:
            out["finish"] = finish

    if row.get("grade"):
        grade = normalize_grade(row["grade"], out.get("material"))
        if grade:
            out["grade"] = grade

    description = row.get("description") or ""
    if "bearing" in description.lower():
        found = _BEARING_IN_TEXT.search(description)
        if found:
            out["bearing"] = normalize_bearing(f"{found.group(1)}-{found.group(2)}")

    return out


def score_pair(query: dict[str, str], candidate: dict[str, str]) -> tuple[float, list[str]]:
    """
    Score a query against one candidate.

    Returns (score, conflicts). A conflict means a different product, so the
    caller rejects the candidate rather than merely penalising it.
    """
    conflicts: list[str] = []
    score = 0.0

    for attribute in DISCRIMINATING:
        left = query.get(attribute)
        right = candidate.get(attribute)
        if not left or not right:
            continue
        # "size" is derived from "thread"; scoring both would double-count.
        if attribute == "size" and query.get("thread") and candidate.get("thread"):
            continue
        if left == right:
            score += WEIGHTS.get(attribute, 5.0)
        else:
            conflicts.append(attribute)

    return score, conflicts


# --- matcher A: fuzzy baseline ---------------------------------------------


class BaselineFuzzyMatcher:
    """
    The existing production matcher: token_sort_ratio over whole descriptions.

    This is the honest incumbent. It is the number any new matcher has to beat,
    and it is included unmodified.
    """

    name = "A_baseline_fuzzy"

    def __init__(self, auto_threshold: float = 85.0,
                 review_threshold: float = 60.0) -> None:
        self.auto_threshold = auto_threshold
        self.review_threshold = review_threshold

    def match(self, row: dict, catalog: Sequence[dict],
              attributes: dict | None = None) -> MatchResult:
        """Score the raw text against every catalog description."""
        if fuzz is None or not catalog:
            return MatchResult(Outcome.GAP, None, 0.0, "no catalog")
        text = row["text"]
        descriptions = [r["description"] for r in catalog]
        found = max(
            ((fuzz.token_sort_ratio(text, d), i) for i, d in enumerate(descriptions)),
            key=lambda pair: pair[0],
        )
        score, index = found
        sku = catalog[index]["sku"]
        if score >= self.auto_threshold:
            return MatchResult(Outcome.AUTO_MATCH, sku, score / 100, f"fuzzy {score:.0f}")
        if score >= self.review_threshold:
            return MatchResult(Outcome.NEEDS_REVIEW, sku, score / 100, f"fuzzy {score:.0f}")
        return MatchResult(Outcome.GAP, None, score / 100, f"best fuzzy {score:.0f}")


# --- matcher B: attribute-based ---------------------------------------------


class AttributeMatcher:
    """
    Match on normalized attribute equality, not on string similarity.

    A candidate is rejected on any conflicting attribute, so 3/8-16 can never
    match 3/8-24 and Zinc can never match Zinc Yellow.
    """

    name = "B_attribute"

    def match(self, row: dict, catalog: Sequence[dict],
              attributes: dict | None = None) -> MatchResult:
        """Compare normalized query attributes against normalized catalog rows."""
        query = normalize_attributes(attributes) if attributes else {}
        if not query:
            return MatchResult(Outcome.GAP, None, 0.0, "no attributes extracted")

        scored: list[tuple[float, str]] = []
        for candidate_row in catalog:
            candidate = catalog_attributes(candidate_row)
            score, conflicts = score_pair(query, candidate)
            if conflicts:
                continue
            scored.append((score, candidate_row["sku"]))

        if not scored:
            return MatchResult(Outcome.GAP, None, 0.0, "every candidate conflicted")

        scored.sort(key=lambda pair: pair[0], reverse=True)
        best_score, best_sku = scored[0]
        runner_up = scored[1] if len(scored) > 1 else None

        if best_score < REVIEW_THRESHOLD:
            return MatchResult(Outcome.GAP, None, best_score / 100, "below review floor")
        if best_score < AUTO_THRESHOLD:
            return MatchResult(
                Outcome.NEEDS_REVIEW, best_sku, best_score / 100,
                f"weak evidence {best_score:.0f}",
            )
        if runner_up and (best_score - runner_up[0]) < AMBIGUITY_MARGIN:
            return MatchResult(
                Outcome.NEEDS_REVIEW, best_sku, best_score / 100,
                f"ambiguous vs {runner_up[1]}",
            )
        return MatchResult(Outcome.AUTO_MATCH, best_sku, best_score / 100,
                           f"attributes agree {best_score:.0f}")


# --- matcher C: hybrid ------------------------------------------------------


class HybridMatcher:
    """
    Attribute matching decides; fuzzy only breaks ties it cannot resolve.

    Fuzzy is deliberately kept on a short leash: it is consulted ONLY among
    candidates that already survived attribute conflict checks, so it can
    reorder survivors but can never rescue a wrong product.
    """

    name = "C_hybrid"

    def match(self, row: dict, catalog: Sequence[dict],
              attributes: dict | None = None) -> MatchResult:
        """Attribute score first, fuzzy similarity as the tiebreak."""
        query = normalize_attributes(attributes) if attributes else {}
        if not query:
            return MatchResult(Outcome.GAP, None, 0.0, "no attributes extracted")

        survivors: list[tuple[float, str, str]] = []
        for candidate_row in catalog:
            candidate = catalog_attributes(candidate_row)
            score, conflicts = score_pair(query, candidate)
            if conflicts:
                continue
            survivors.append((score, candidate_row["sku"],
                              candidate_row.get("description", "")))

        if not survivors:
            return MatchResult(Outcome.GAP, None, 0.0, "every candidate conflicted")

        survivors.sort(key=lambda item: item[0], reverse=True)
        best_score, best_sku, best_text = survivors[0]

        if best_score < REVIEW_THRESHOLD:
            return MatchResult(Outcome.GAP, None, best_score / 100, "below review floor")

        # Only consult fuzzy when attributes leave more than one plausible row.
        # Fuzzy picks only among candidates with NO attribute conflicts, so a
        # near-lookalike with a wrong spec cannot be smuggled in this way --
        # the blast radius is confined to the tie set.
        if len(survivors) > 1 and (best_score - survivors[1][0]) < AMBIGUITY_MARGIN:
            tied = [s for s in survivors if best_score - s[0] < AMBIGUITY_MARGIN]
            if fuzz is not None:
                picked = max(
                    tied,
                    key=lambda item: fuzz.token_sort_ratio(row["text"], item[2]),
                )
                return MatchResult(
                    Outcome.AUTO_MATCH, picked[1], best_score / 100,
                    f"fuzzy broke {len(tied)}-way tie",
                )
            return MatchResult(Outcome.NEEDS_REVIEW, best_sku, best_score / 100,
                               "unresolved tie, no fuzzy available")

        if best_score < AUTO_THRESHOLD:
            return MatchResult(Outcome.NEEDS_REVIEW, best_sku, best_score / 100,
                               f"weak evidence {best_score:.0f}")
        return MatchResult(Outcome.AUTO_MATCH, best_sku, best_score / 100,
                           f"attributes agree {best_score:.0f}")


def build_matchers() -> list[Matcher]:
    """All three matchers, in report order."""
    return [BaselineFuzzyMatcher(), AttributeMatcher(), HybridMatcher()]
