"""Deterministic attribute extraction from free-text industrial descriptions.

The LLM (or pdfplumber) gives us messy text. This module turns that text into a
fixed set of comparable attributes using rules only -- no model calls, no
network, fully unit-testable and deterministic.

Design rule: an attribute is only emitted when the text gives enough evidence.
Silence is meaningful. A missing attribute never blocks a match, but a
*conflicting* attribute always rejects one.
"""

import re
from typing import Final

# --- family -----------------------------------------------------------------

_FAMILY_RULES: Final[list[tuple[str, re.Pattern[str]]]] = [
    ("hex_bolt", re.compile(r"\bhex\s*bolt\b|\bbolt\b|\bcap\s*screw\b", re.I)),
    ("hex_nut", re.compile(r"\bhex\s*nut\b|\bnut\b", re.I)),
    ("flat_washer", re.compile(r"\bflat\s*washer\b|\bwasher\b", re.I)),
    ("ball_bearing", re.compile(r"\bball\s*bearing\b|\bbearing\b", re.I)),
    ("ball_valve", re.compile(r"\bball\s*valve\b", re.I)),
    ("globe_valve", re.compile(r"\bglobe\s*valve\b", re.I)),
    ("emt_connector", re.compile(r"\bconnector\b", re.I)),
    ("emt_conduit", re.compile(r"\bconduit\b", re.I)),
    ("cable_tie", re.compile(r"\bcable\s*tie\b|\bty[\s-]*wrap\b", re.I)),
    ("thhn_wire", re.compile(r"\bthhn\b", re.I)),
    ("wire", re.compile(r"\bwire\b", re.I)),
    ("pvc_pipe", re.compile(r"\bpvc\b", re.I)),
    ("safety_glasses", re.compile(r"\bsafety\s*glasses\b|\bglasses\b|\bgoggles\b", re.I)),
    ("strut_channel", re.compile(r"\bstrut\b|\bchannel\b", re.I)),
]

# --- size ------------------------------------------------------------------

_FRACTION_RE: Final = re.compile(r"\b(\d{1,2})-(\d{1,2})/(\d{1,2})\b")
_METRIC_RE: Final = re.compile(r"\bM(\d{1,2})\b", re.I)
_BARE_FRACTION_RE: Final = re.compile(r"\b(\d)\s*/\s*(\d{1,2})\b")
_THREAD_RE: Final = re.compile(
    r"\b(\d{1,2})\s*/\s*(\d{1,2})\s*-\s*(\d{1,2})\b"  # 3/8-16
    r"|\b(\d)\s*/\s*(\d{1,2})\s+(\d{1,2})\b",          # 3/8 16
    re.I,
)
_BEARING_RE: Final = re.compile(r"\b(\d{4})\s*-?\s*(\d[A-Z]{1,2})\b", re.I)

# --- length ----------------------------------------------------------------

_LENGTH_FRACTION_RE: Final = re.compile(
    r"\bx\s*(\d)-(\d{1,2})/(\d{1,2})\b"      # x 3-1/2
    r"|\b(\d)\s*-\s*(\d{1,2})/(\d{1,2})\b",  # 1-1/4
    re.I,
)
_LENGTH_DECIMAL_RE: Final = re.compile(
    r"\bx\s*(\d+(?:\.\d+)?)\b"
    r"|\b(\d+(?:\.\d+)?)\s*(?:in\b|inch)"
    r"|\blength\s*(\d+(?:\.\d+)?)\b",
    re.I,
)

# --- finish / material -----------------------------------------------------

_FINISH_RULES: Final[list[tuple[str, re.Pattern[str]]]] = [
    ("Zinc", re.compile(r"\bzinc\b|\bplated\b|\bcr\+?3\b|\bcr3\b", re.I)),
    ("Stainless", re.compile(r"\bstainless\b|\bss\b", re.I)),
    ("Galvanized", re.compile(r"\bgalv(?:anized)?\b", re.I)),
    ("Brass", re.compile(r"\bbrass\b", re.I)),
    ("Bronze", re.compile(r"\bbronze\b", re.I)),
    ("PVC", re.compile(r"\bpvc\b", re.I)),
    ("Clear", re.compile(r"\bclear\b", re.I)),
    ("Black", re.compile(r"\bblack\b", re.I)),
    ("White", re.compile(r"\bwhite\b", re.I)),
]

_GRADE_RE: Final = re.compile(r"\b(316|304)\b", re.I)
_PRESSURE_RE: Final = re.compile(r"\b(\d{3})\s*#?\b")

def _normalize_size(value: str) -> str:
    """Render a fractional or metric size in one canonical string form."""
    return re.sub(r"\s+", "", value).lower()


def canonicalize(attributes: dict[str, str]) -> dict[str, str]:
    """
    Normalise attribute values so both sides of a comparison agree.

    Extraction produces human-readable values ("Zinc", "2.0") while catalog
    columns hold whatever the customer typed ("zinc", "2"). Comparing those raw
    would report a false conflict, so every value passes through here first.
    """
    canonical: dict[str, str] = {}
    for key, value in attributes.items():
        text = str(value).strip().lower()
        if not text:
            continue
        if key == "length":
            # "2.0", "2.00" and "2" are the same length.
            try:
                text = f"{float(text):g}"
            except ValueError:
                pass
        elif key == "diameter":
            text = _normalize_size(text)
        canonical[key] = text
    return canonical


def extract_attributes(text: str) -> dict[str, str]:
    """
    Parse a free-text description into comparable attributes.

    Only attributes with explicit evidence are emitted, so callers can tell
    "not mentioned" apart from "contradicted".
    """
    raw = text.strip()
    attributes: dict[str, str] = {}

    for family, pattern in _FAMILY_RULES:
        if pattern.search(raw):
            attributes["family"] = family
            break

    # Thread / size pair, e.g. "3/8-16" or "3/8 16".
    diameter: str | None = None
    pitch: str | None = None
    thread_match = _THREAD_RE.search(raw)
    if thread_match:
        groups = [g for g in thread_match.groups() if g]
        diameter = f"{groups[0]}/{groups[1]}"
        pitch = groups[2]

    metric = _METRIC_RE.search(raw)
    if metric and diameter is None:
        diameter = f"M{metric.group(1)}"

    mixed = _FRACTION_RE.search(raw)
    if diameter is not None:
        attributes["diameter"] = _normalize_size(diameter)
        attributes["thread_pitch"] = pitch or ""
    elif mixed:
        attributes["diameter"] = f"{mixed.group(1)}-{mixed.group(2)}/{mixed.group(3)}"
    else:
        bare = _BARE_FRACTION_RE.search(raw)
        inches = re.search(r"\b(\d)\s*(?:in\b|inch)", raw, re.I)
        if bare:
            attributes["diameter"] = f"{bare.group(1)}/{bare.group(2)}"
        elif inches:
            attributes["diameter"] = f"{inches.group(1)}"

    bearing = _BEARING_RE.search(raw)
    if bearing:
        attributes["bearing"] = f"{bearing.group(1)}-{bearing.group(2).upper()}"

    length_fraction = _LENGTH_FRACTION_RE.search(raw)
    if length_fraction and length_fraction.group(1):
        whole = int(length_fraction.group(1))
        attributes["length"] = _decimal_length(
            whole, int(length_fraction.group(2)), int(length_fraction.group(3))
        )
    elif length_fraction and length_fraction.group(4):
        whole = int(length_fraction.group(4))
        attributes["length"] = _decimal_length(
            whole, int(length_fraction.group(5)), int(length_fraction.group(6))
        )
    else:
        length_decimal = _LENGTH_DECIMAL_RE.search(raw)
        if length_decimal:
            value = next(g for g in length_decimal.groups() if g)
            if value not in _LENGTH_STOPWORDS:
                attributes["length"] = str(float(value))

    for finish, pattern in _FINISH_RULES:
        if pattern.search(raw):
            attributes["finish"] = finish
            break

    grade = _GRADE_RE.search(raw)
    if grade:
        attributes["material"] = grade.group(1)

    pressure = _PRESSURE_RE.search(raw)
    if pressure:
        attributes["pressure"] = pressure.group(1)

    return attributes


def _decimal_length(whole: int, numerator: int, denominator: int) -> str:
    """Render a mixed-fraction length like 3-1/2 as a decimal string."""
    return str(whole + numerator / denominator)

# Numbers that look like lengths but are codes, ratings or gauges.
_LENGTH_STOPWORDS: Final[frozenset[str]] = frozenset(
    {"600", "125", "150", "316", "304", "203", "204", "205", "206"}
)
