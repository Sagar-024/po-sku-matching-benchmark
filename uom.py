"""Pack-size and unit-of-measure conversion.

This is a real factor table, not a synonym map. It answers "how many pieces are
in a carton?", which a synonym map can never answer.

Two sources of truth are handled:
  1. `PACK_FACTORS` -- standard distributor pack conventions.
  2. the catalog's own `pack_size` column -- authoritative for that SKU.

Where a unit is genuinely customer-defined (a "box" of what?), the conversion
REFUSES rather than guessing, because a wrong pack factor corrupts order
quantities.
"""

from __future__ import annotations

from typing import Final


class ConversionError(ValueError):
    """A pack conversion was requested that has no defined answer."""


PIECE: Final = "piece"
FOOT: Final = "foot"

# canonical unit -> (base kind, base units per 1 of this unit)
PACK_FACTORS: Final[dict[str, tuple[str, float]]] = {
    # piece counts
    "ea": (PIECE, 1.0), "each": (PIECE, 1.0), "pc": (PIECE, 1.0),
    "pcs": (PIECE, 1.0), "piece": (PIECE, 1.0), "pieces": (PIECE, 1.0),
    "dz": (PIECE, 12.0), "dozen": (PIECE, 12.0),
    "pack": (PIECE, 25.0), "pk": (PIECE, 25.0),
    "carton": (PIECE, 50.0), "ctn": (PIECE, 50.0),
    "case": (PIECE, 48.0), "cs": (PIECE, 48.0),
    "pallet": (PIECE, 1000.0), "pl": (PIECE, 1000.0),
    "hundred": (PIECE, 100.0), "c": (PIECE, 100.0),
    "gross": (PIECE, 144.0), "gr": (PIECE, 144.0),
    # length-based
    "ft": (FOOT, 1.0), "foot": (FOOT, 1.0), "feet": (FOOT, 1.0),
    "roll": (FOOT, 100.0), "reel": (FOOT, 1000.0), "spool": (FOOT, 1000.0),
}

# Units whose size depends entirely on the product, so no factor is safe.
AMBIGUOUS: Final[frozenset[str]] = frozenset({"box", "bx"})

_UNIT_ALIASES: Final[dict[str, str]] = {
    "boxes": "box", "cartons": "carton", "cases": "case", "packs": "pack",
    "dozens": "dozen", "rolls": "roll", "eaches": "each", "ea.": "ea",
}


def canonical_unit(unit: str) -> str:
    """Lowercase, strip punctuation, and resolve simple plurals."""
    key = str(unit or "").strip().lower().rstrip(".")
    return _UNIT_ALIASES.get(key, key)


def pack_factor(unit: str) -> tuple[str, float] | None:
    """
    Return (base kind, factor) for a unit, or None when the unit is unknown.

    Raises ConversionError for customer-defined units, because guessing their
    size would silently corrupt quantities.
    """
    key = canonical_unit(unit)
    if not key:
        return None
    if key in AMBIGUOUS:
        raise ConversionError(
            f"'{unit}' is customer-defined; its size must come from the catalog"
        )
    return PACK_FACTORS.get(key)


def convert(quantity: float, from_unit: str, to_unit: str) -> float:
    """
    Convert a quantity between units of the same kind.

    Raises ConversionError for unknown units, customer-defined units, or an
    attempt to convert pieces into feet.
    """
    source = pack_factor(from_unit)
    target = pack_factor(to_unit)
    if source is None:
        raise ConversionError(f"unknown unit '{from_unit}'")
    if target is None:
        raise ConversionError(f"unknown unit '{to_unit}'")
    if source[0] != target[0]:
        raise ConversionError(
            f"cannot convert {source[0]}s to {target[0]}s "
            f"('{from_unit}' -> '{to_unit}')"
        )
    result = quantity * source[1] / target[1]
    return int(result) if float(result).is_integer() else round(result, 6)


def to_eaches(quantity: float, unit: str, catalog_pack_size: int | None = None) -> float:
    """
    Convert a PO quantity to eaches.

    The catalog's own pack size wins for container units, because a
    distributor's "box" or "carton" is whatever that distributor says it is.
    Generic table factors apply everywhere else.
    """
    key = canonical_unit(unit)
    if catalog_pack_size and catalog_pack_size > 1 and key in _CONTAINER_UNITS:
        result = quantity * catalog_pack_size
        return int(result) if float(result).is_integer() else round(result, 6)
    return convert(quantity, unit, "ea")


_CONTAINER_UNITS: Final[frozenset[str]] = frozenset(
    {"box", "carton", "case", "pack", "pallet", "dozen"}
)


def pack_factor_or_none(unit: str) -> tuple[str, float] | None:
    """Like pack_factor but returns None instead of raising for ambiguous units."""
    try:
        return pack_factor(unit)
    except ConversionError:
        return None


def uom_matches(po_unit: str, catalog_unit: str,
                catalog_pack_size: int | None = None) -> bool:
    """
    Report whether a PO unit and catalog unit mean the same pack size.

    Unknown or empty units are treated as "no evidence", never as a mismatch,
    so a missing unit never manufactures an ERP blocker.
    """
    if not canonical_unit(po_unit) or not canonical_unit(catalog_unit):
        return True
    try:
        convert(1.0, po_unit, catalog_unit)
        return True
    except ConversionError:
        if catalog_pack_size and catalog_pack_size > 1:
            po_factor = pack_factor_or_none(po_unit)
            return po_factor is None or po_factor[1] == catalog_pack_size
        return False
