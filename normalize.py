"""Deterministic normalization of fastener/valve/bearing attributes.

The LLM extracts *raw* attributes from messy text. This module turns those raw
values into canonical forms so equality comparison is meaningful:

    3/8      -> 0.375          (fraction to decimal)
    3/8-16   -> size 0.375, twist 16 TPI
    M10x1.5  -> size m10,     twist 1.5 mm
    Zn       -> "zinc"         (finish synonym)
    Gr5      -> "grade 5"

Everything here is pure, offline and unit-tested. No model calls, no network.
"""

from __future__ import annotations

import re
from typing import Final

# --- synonym tables ---------------------------------------------------------

FINISH_SYNONYMS: Final[dict[str, str]] = {
    "zinc": "zinc", "zn": "zinc", "zinc plated": "zinc", "zinc plate": "zinc",
    "zn pltd": "zinc", "zn plated": "zinc",
    "electro zinc": "zinc", "cr+3": "zinc", "cr3": "zinc", "clear zinc": "zinc",
    "zinc yellow": "zinc yellow", "yellow zinc": "zinc yellow",
    "zn yel": "zinc yellow", "yellow chromate": "zinc yellow",
    "plain": "plain", "bare": "plain", "uncoated": "plain",
    "black oxide": "plain", "hot dip galvanized": "plain",
    "verzinkt": "zinc", "gelb verzinkt": "zinc yellow",
}

MATERIAL_SYNONYMS: Final[dict[str, str]] = {
    "steel": "steel", "carbon steel": "steel", "cstl": "steel", "cs": "steel",
    "stainless": "stainless", "stainless steel": "stainless", "ss": "stainless",
    "a2": "stainless", "a4": "stainless", "edelstahl": "stainless",
    "brass": "brass", "bronze": "bronze", "pvc": "pvc",
    "bearing steel": "bearing steel",
}

TYPE_SYNONYMS: Final[dict[str, str]] = {
    "hex bolt": "hex bolt", "hx blt": "hex bolt", "hex head bolt": "hex bolt",
    "sechskantschraube": "hex bolt", "bolt": "hex bolt",
    "hex nut": "hex nut", "hx nut": "hex nut", "sechskantmutter": "hex nut",
    "flat washer": "flat washer", "flat wshr": "flat washer",
    "washer": "flat washer",
    "socket head cap screw": "socket head cap screw",
    "shcs": "socket head cap screw", "setzkopfschraube": "socket head cap screw",
    "cap screw": "socket head cap screw",
    "deep groove ball bearing": "deep groove ball bearing",
    "dgbb": "deep groove ball bearing", "ball bearing": "deep groove ball bearing",
    "bearing": "deep groove ball bearing",
    "ball valve": "ball valve", "ball vlv": "ball valve",
    "globe valve": "globe valve", "globe vlv": "globe valve",
    "elbow 90": "elbow 90", "elb90": "elbow 90", "elbow": "elbow 90",
    "tee": "tee", "coupling": "coupling", "cplg": "coupling",
    "reducer": "reducer", "rdc": "reducer",
}

_FRACTION = re.compile(r"^(\d+)\s*/\s*(\d+)$")
_MIXED = re.compile(r"^(\d+)\s*-\s*(\d+)\s*/\s*(\d+)$")
_METRIC = re.compile(r"^m\s*(\d+(?:\.\d+)?)$", re.I)
_PLAIN_NUMBER = re.compile(r"^(\d+(?:\.\d+)?)$")

# Coarse-thread pitches stop well below 6 mm for the sizes stocked here; any
# second number at or above this bound on an "MxN" pair is a length, not a
# pitch. Anything above the largest common coarse pitch (5.0 on M80) is not a
# thread.
_MAX_THREAD_PITCH_MM: Final[float] = 6.0


def _norm_key(value: str) -> str:
    """Lowercase, collapse whitespace and strip trailing punctuation."""
    return re.sub(r"\s+", " ", str(value).strip().lower()).strip(".#? ")


def normalize_fraction(value: str) -> float | None:
    """Convert an imperial size to inches as a float, or None if unrecognisable."""
    text = _norm_key(value).replace('"', "").replace("in", "").strip()
    if not text:
        return None

    mixed = _MIXED.match(text)
    if mixed:
        whole, numerator, denominator = (int(g) for g in mixed.groups())
        return round(whole + numerator / denominator, 6) if denominator else None

    fraction = _FRACTION.match(text)
    if fraction:
        numerator, denominator = (int(g) for g in fraction.groups())
        return round(numerator / denominator, 6) if denominator else None

    plain = _PLAIN_NUMBER.match(text)
    return round(float(plain.group(1)), 6) if plain else None


def normalize_length(value: str) -> float | None:
    """Convert a length to inches as a float; a bare number is read as inches."""
    text = _norm_key(value)
    if not text:
        return None
    metric = re.search(r"(\d+(?:\.\d+)?)\s*mm\b", text)
    if metric:
        return round(float(metric.group(1)) / 25.4, 6)
    text = re.sub(r"\b(in|inch|inches)\b", "", text).replace('"', "").strip()
    return normalize_fraction(text)



def normalize_size(value: str) -> str | None:
    """
    Canonicalize a nominal size.

    Imperial becomes inches as a decimal string ("3/8" -> "0.375"). Metric
    keeps an "m" prefix so 10 mm can never equal 10 inches.
    """
    text = _norm_key(value)
    if not text:
        return None
    text = _repair_leading_slash(text)
    metric = _METRIC.match(text)
    if metric:
        return f"m{float(metric.group(1)):g}"
    if re.match(r"^\d+(?:\.\d+)?\s*mm$", text):
        return f"m{float(text.split('mm')[0].strip()):g}"
    inches = normalize_fraction(text)
    return f"{inches:g}" if inches is not None else None


def _repair_leading_slash(text: str) -> str:
    """
    Repair a size fragment damaged by abbreviation or typo.

    Observed damage: catalog "3/4" rendered by a PO writer as "/34", i.e. the
    slash was dropped and the digits concatenated. A 2-digit "/NN" is tried as
    numerator/denominator splits, preferring sizes that actually exist on an
    inch ruler (denominators 2, 4, 8, 16).
    """
    damaged = re.match(r"^/(\d)(\d)$", text)
    if not damaged:
        return text
    numerator, denominator = damaged.group(1), damaged.group(2)
    if denominator in ("2", "4", "8"):
        return f"{numerator}/{denominator}"
    return text
    return text


def normalize_thread(value: str) -> tuple[str | None, str | None]:
    """
    Split a thread spec into (size, pitch).

    "3/8-16" -> ("0.375", "16");  "M10x1.5" -> ("m10", "1.5").
    Pitch stays a string because TPI and millimetres are different scales.
    """
    text = _norm_key(value)
    if not text:
        return None, None

    metric = re.match(r"^m\s*(\d+(?:\.\d+)?)\s*[x*-]\s*(\d+(?:\.\d+)?)$", text)
    if metric:
        second = float(metric.group(2))
        if second <= _MAX_THREAD_PITCH_MM:
            return f"m{float(metric.group(1)):g}", f"{second:g}"
        # "M10x40" is diameter x length, not diameter x pitch.
        return f"m{float(metric.group(1)):g}", None

    imperial = re.match(r"^(\d+\s*/\s*\d+|\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$", text)
    if imperial:
        size = normalize_fraction(imperial.group(1))
        if size is not None:
            return f"{size:g}", f"{float(imperial.group(2)):g}"

    return normalize_size(text), None


def _synonym_lookup(value: str, table: dict[str, str]) -> str | None:
    """Exact match first, then longest-substring match so phrases beat words."""
    key = _norm_key(value)
    if not key:
        return None
    if key in table:
        return table[key]
    for synonym in sorted(table, key=len, reverse=True):
        if synonym in key:
            return table[synonym]
    return None


def normalize_finish(value: str) -> str | None:
    """Map a finish, abbreviation or German term to a canonical finish."""
    return _synonym_lookup(value, FINISH_SYNONYMS)


def normalize_material(value: str) -> str | None:
    """Map a material or temper code to a canonical material."""
    return _synonym_lookup(value, MATERIAL_SYNONYMS)


def normalize_type(value: str) -> str | None:
    """Map a product type or abbreviation to a canonical type."""
    return _synonym_lookup(value, TYPE_SYNONYMS)


def normalize_grade(value: str, material: str | None = None) -> str | None:
    """
    Canonicalize a strength grade.

    Imperial ("Grade 5") and metric ("8.8") scales stay distinct: they are not
    equivalent, so treating them as equal would manufacture false matches.
    """
    key = _norm_key(value).replace("gr", "grade ").replace("klasse", "grade ")
    if not key:
        return None
    if material == "stainless":
        if "a2" in key or "70" in key:
            return "a2-70"
        if "a4" in key or "80" in key:
            return "a4-80"
    number = re.search(r"(\d+(?:\.\d+)?)", key)
    if not number:
        return key
    numeric = float(number.group(1))
    if numeric in (5.0, 8.0, 2.0):
        return f"grade {numeric:g}"
    return f"{numeric:g}"


def normalize_bearing(value: str, suffix: str = "") -> str | None:
    """
    Canonicalize a bearing designation.

    "6203-2RS" -> "6203-2rs". Basic number and seal suffix stay separate so
    6203-2RS never equals 6203-2Z.
    """
    text = _norm_key(value).replace(" ", "")
    if not text:
        return None
    match = re.match(r"^(\d{4})\s*-?\s*([a-z0-9]{0,4})$", text)
    if not match:
        return text
    number, seal = match.group(1), match.group(2)
    if not seal and suffix:
        seal = _norm_key(suffix).lstrip("-")
    return f"{number}-{seal}" if seal else number
