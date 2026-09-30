"""Generate the synthetic benchmark dataset for PO-to-SKU matching.

This script is the ONLY source of ground truth. Labels come from the source
record that produced each description, never from any matcher's output.

Order of operations:
  1. build catalog      -> data/catalog.csv
  2. build descriptions -> data/dev.csv (100) and data/test.csv (200)
  3. freeze             -> data/manifest.json records the test SHA256

The test split is written and hashed BEFORE any matcher is written. Never edit
data/test.csv after that point; if a bug forces a change, report both runs
instead of silently re-freezing.

ALL DATA IS SYNTHETIC. It imitates distributor wording; it is not a real
catalog and contains no real customer data.

Run from the project root:
    python generate_dataset.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

SEED = 20260930
BENCH = Path(__file__).parent
DATA = BENCH / "data"
DEV_COUNT = 100
TEST_COUNT = 200
GAP_FRACTION = 0.15


@dataclass
class CatalogRow:
    """One SKU with structured attributes; its description derives from them."""

    sku: str
    description: str
    category: str
    type: str
    size: str
    thread: str
    length: str
    material: str
    finish: str
    grade: str
    uom: str
    pack_size: int
    lang: str = "en"


@dataclass
class PoRow:
    """One labeled PO line. expected_sku is empty exactly when is_gap is true."""

    id: str
    text: str
    expected_sku: str
    is_gap: bool
    category: str
    style: str
    split: str
    po_uom: str = ""
    po_quantity: float = 0.0
    expected_base_qty: float = 0.0
    source_sku: str = ""
    meta: dict = field(default_factory=dict)


# --- catalog vocabulary -----------------------------------------------------

# 3/8-16 vs 3/8-24 and 1/2-13 vs 1/2-20 are thread-pitch hard negatives.
IMPERIAL_THREADS = [
    ("1/4", "20"), ("1/4", "28"), ("5/16", "18"), ("3/8", "16"),
    ("3/8", "24"), ("7/16", "14"), ("1/2", "13"), ("1/2", "20"),
    ("5/8", "11"), ("3/4", "10"),
]
IMPERIAL_LENGTHS = ["0.5", "0.75", "1", "1.25", "1.5", "2", "2.5", "3", "3.5", "4"]
# Zinc vs Zinc Yellow and Grade 5 vs Grade 8 are the finish/grade negatives.
FINISHES = ["Plain", "Zinc", "Zinc Yellow"]
GRADES_IMP = ["Grade 5", "Grade 8"]
METRIC_THREADS = [("M6", "1.0"), ("M8", "1.25"), ("M10", "1.5"), ("M12", "1.75")]
METRIC_LENGTHS = ["16", "20", "25", "30", "35", "40", "50", "60", "80"]
GRADES_MET = ["8.8", "10.9", "A2-70"]
BEARING_SIZES = ["6000", "6001", "6002", "6003", "6004", "6005", "6006",
                 "6200", "6201", "6202", "6203", "6204", "6205", "6206",
                 "6300", "6301", "6302", "6303", "6304", "6800", "6801"]
BEARING_SUFFIX = ["-2RS", "-2Z", "-ZZ"]
VALVE_SIZES = ["1/8", "1/4", "3/8", "1/2", "3/4", "1", "1-1/4", "1-1/2", "2"]
VALVE_MATERIALS = ["Brass", "Bronze", "Stainless Steel", "Carbon Steel"]
VALVE_PRESSURES = ["125#", "150#", "200#", "300#"]
FIT_SIZES = ["1/4", "3/8", "1/2", "3/4", "1", "1-1/4", "1-1/2", "2"]
FIT_MATERIALS = ["Carbon Steel", "Stainless Steel", "Brass", "PVC"]
FIT_TYPES = ["Elbow 90", "Tee", "Coupling", "Reducer"]


# --- catalog ----------------------------------------------------------------


def _sku(prefix: str, *parts: object) -> str:
    """Compact SKU from discriminative parts only."""
    return "-".join([prefix] + [str(p).replace("/", "").replace(".", "")
                                .replace("#", "").replace("-", "")
                                for p in parts if str(p)])


def _build_pool() -> list[CatalogRow]:
    """Enumerate every catalog combination we could ever want."""
    pool: list[CatalogRow] = []

    for size, pitch in IMPERIAL_THREADS:
        for length in IMPERIAL_LENGTHS:
            for finish in FINISHES:
                for grade in GRADES_IMP:
                    pool.append(CatalogRow(
                        sku=_sku("HB", size, pitch, length, grade, finish),
                        description=f"Hex Bolt {size}-{pitch} x {length}\" "
                                    f"{grade} {finish} Hex Head",
                        category="fastener", type="Hex Bolt",
                        size=size, thread=f"{size}-{pitch}", length=length,
                        material="Steel", finish=finish, grade=grade,
                        uom="Ea", pack_size=1,
                    ))

    for size, pitch in METRIC_THREADS:
        for length in METRIC_LENGTHS:
            for grade in GRADES_MET:
                pool.append(CatalogRow(
                    sku=_sku("HBM", size, length, grade),
                    description=f"Hex Bolt {size}x{length} {grade} ISO 4762 "
                                f"Zinc Plated",
                    category="fastener", type="Hex Bolt",
                    size=size, thread=f"{size}-{pitch}", length=length,
                    material="Steel", finish="Zinc", grade=grade,
                    uom="Ea", pack_size=1,
                ))
                pool.append(CatalogRow(
                    sku=_sku("SHCS", size, length, grade),
                    description=f"Setzkopfschraube {size}x{length} {grade} DIN 912",
                    category="fastener", type="Socket Head Cap Screw",
                    size=size, thread=f"{size}-{pitch}", length=length,
                    material="Steel", finish="Zinc", grade=grade,
                    lang="de", uom="Ea", pack_size=1,
                ))

    for size, pitch in IMPERIAL_THREADS:
        for grade in GRADES_IMP:
            pool.append(CatalogRow(
                sku=_sku("HN", size, pitch, grade),
                description=f"Hex Nut {size}-{pitch} ASME B18.2.2 {grade}",
                category="fastener", type="Hex Nut",
                size=size, thread=f"{size}-{pitch}", length="",
                material="Steel", finish="Zinc", grade=grade,
                uom="Ea", pack_size=1,
            ))
        pool.append(CatalogRow(
            sku=_sku("FW", size),
            description=f"Flat Washer {size} ASME B18.21.1 Zinc",
            category="fastener", type="Flat Washer",
            size=size, thread="", length="",
            material="Steel", finish="Zinc", grade="",
            uom="Ea", pack_size=1,
        ))

    for size in BEARING_SIZES:
        for suffix in BEARING_SUFFIX:
            pool.append(CatalogRow(
                sku=_sku("BRG", size, suffix),
                description=f"Deep Groove Ball Bearing {size}{suffix}",
                category="bearing", type="Deep Groove Ball Bearing",
                size=size, thread="", length="",
                material="Bearing Steel", finish="Chrome", grade="",
                uom="Ea", pack_size=1,
            ))

    for size in VALVE_SIZES:
        for material in VALVE_MATERIALS:
            for pressure in VALVE_PRESSURES:
                pool.append(CatalogRow(
                    sku=_sku("GV", size, material, pressure),
                    description=f"Globe Valve {size} {material} {pressure} Flanged",
                    category="valve", type="Globe Valve",
                    size=size, thread="", length="",
                    material=material, finish="", grade=pressure,
                    uom="Ea", pack_size=1,
                ))
        for material in ("Brass", "Stainless Steel"):
            pool.append(CatalogRow(
                sku=_sku("BV", size, material),
                description=f"Ball Valve {size} {material} 2-Way Full Port",
                category="valve", type="Ball Valve",
                size=size, thread="", length="",
                material=material, finish="", grade="",
                uom="Ea", pack_size=1,
            ))

    for size in FIT_SIZES:
        for material in FIT_MATERIALS:
            for kind in FIT_TYPES:
                for pack, uom in ((1, "Ea"), (10, "Box"), (50, "Carton")):
                    pool.append(CatalogRow(
                        sku=_sku("FT", kind, size, material, pack),
                        description=f"{material} {kind} {size}\" Sch 40",
                        category="fitting", type=kind,
                        size=size, thread="", length="",
                        material=material, finish="", grade="Sch 40",
                        uom=uom, pack_size=pack,
                    ))
    return pool


def build_catalog(target: int = 275) -> list[CatalogRow]:
    """
    Cap the pool at `target` SKUs deterministically.

    Force-include the rows that hard-negative queries depend on, so every
    designed trap still has a correct answer present after sampling.
    """
    pool = _build_pool()
    rng = random.Random(SEED)

    # Rows the hard-negative queries require as their correct answer.
    required_threads = {"3/8-16", "3/8-24", "1/2-13", "1/2-20"}
    must_keep = [
        r for r in pool
        if (r.type == "Hex Bolt" and r.thread in required_threads
            and r.material == "Steel" and r.grade == "Grade 5"
            and r.finish in {"Zinc", "Zinc Yellow"}
            and r.length in {"1.5", "2", "3"})
        # One complete grade/finish family for the grade-5 vs grade-8 trap.
        or (r.type == "Hex Bolt" and r.size == "3/8" and r.thread == "3/8-16"
            and r.finish == "Zinc" and r.length == "2")
    ]
    keep = {r.sku for r in must_keep}

    # Bucket the remainder so sampling preserves every category and style.
    buckets: dict[str, list[CatalogRow]] = {}
    for row in pool:
        if row.sku in keep:
            continue
        buckets.setdefault(row.category, []).append(row)
    for bucket in buckets.values():
        rng.shuffle(bucket)

    remaining = target - len(keep)
    per_bucket = max(1, remaining // max(1, len(buckets)))
    chosen = {r.sku: r for r in must_keep}
    for bucket in buckets.values():
        for row in bucket[:per_bucket]:
            chosen[row.sku] = row

    # Top up if rounding left us short.
    if len(chosen) < target:
        for bucket in buckets.values():
            for row in bucket[per_bucket:]:
                if len(chosen) >= target:
                    break
                chosen.setdefault(row.sku, row)
            if len(chosen) >= target:
                break

    catalog = sorted(chosen.values(), key=lambda r: r.sku)
    if not 150 <= len(catalog) <= 300:
        raise SystemExit(f"catalog size {len(catalog)} is outside 150-300")
    return catalog


# --- messy PO description styles -------------------------------------------
# Each style is a deliberate, reproducible way of saying the same thing. The
# label never comes from a matcher: it comes from the row we rendered from.


def _abbreviate(text: str) -> str:
    """Trade distributor short-hand for the catalog's full words."""
    swaps = [
        ("Hex Bolt", "Hx Blt"), ("Socket Head Cap Screw", "SHCS"),
        ("Hex Nut", "Hx Nut"), ("Flat Washer", "Flat Wshr"),
        ("Ball Valve", "Ball Vlv"), ("Globe Valve", "Globe Vlv"),
        ("Deep Groove Ball Bearing", "DGBB"),
        ("Elbow 90", "Elb90"), ("Coupling", "Cplg"), ("Reducer", "Rdc"),
        ("Stainless Steel", "SS"), ("Carbon Steel", "CStl"),
        ("Schedule 40", "Sch40"), ("Zinc Yellow", "Zn Yel"),
        ("Grade 5", "Gr5"), ("Grade 8", "Gr8"),
        (" Full Port", ""), (" Flanged", ""), (" Hex Head", ""),
        ("Deep Groove Ball Bearing", "DGBB"),
        (" inch", "\""), ("Zinc Plated", "Zn Pltd"),
        (" Setzkopfschraube", " SHCS"),
    ]
    out = text
    for long, short in swaps:
        out = out.replace(long, short)
    return out


def _shuffle_words(text: str, rng: random.Random) -> str:
    """Reorder words; meaning survives, token order does not."""
    words = text.split()
    if len(words) < 3:
        return text
    head, tail = words[0], words[1:]
    rng.shuffle(tail)
    return " ".join([head, *tail])


def _typo(text: str, rng: random.Random) -> str:
    """One or two realistic keystroke errors."""
    swaps = {"a": "s", "e": "w", "i": "o", "o": "p", "s": "a", "t": "y",
             "m": "n", "n": "m", "l": "k", "r": "f"}
    out = list(text)
    for _ in range(rng.randint(1, 2)):
        idx = rng.randrange(len(out))
        char = out[idx].lower()
        if char in swaps:
            out[idx] = swaps[char]
        elif char == " ":
            continue
        elif idx + 1 < len(out):
            out[idx], out[idx + 1] = out[idx + 1], out[idx]
    return "".join(out)


def _drop_units(text: str) -> str:
    """Strip inch/mm markers, a very common email-in-a-PO error."""
    for marker in (" mm", " MM", " inch", "in ", "\""):
        text = text.replace(marker, " ")
    return " ".join(text.split())


def _to_imperial(text: str, row: CatalogRow) -> str:
    """Metric sizes written the way a US branch would type them."""
    if row.size.startswith("M") and row.length:
        return text.replace(f"{row.size}x{row.length}", f"{row.size[1:]}mm x {row.length}mm")
    return text


GERMAN_MAP = [
    ("Hex Bolt", "Sechskantschraube"), ("Hex Nut", "Sechskantmutter"),
    ("Flat Washer", "Flachscheibe"), ("Zinc", "verzinkt"),
    ("Zinc Yellow", "gelb verzinkt"), ("Stainless", "Edelstahl"),
    ("Grade 5", "Klasse 8.8"), ("Grade 8", "Klasse 10.9"),
]


def _to_german(text: str) -> str:
    """German nomenclature as a Bavarian branch would write it."""
    out = text
    for long, short in GERMAN_MAP:
        out = out.replace(long, short)
    return out


def _customer_part_number(row: CatalogRow, rng: random.Random) -> str:
    """The customer's internal number, which shares no words with our catalog."""
    prefix = rng.choice(("PN", "INT", "SKU", "CUST"))
    digits = f"{rng.randrange(10000, 99999)}"
    suffix = rng.choice(("", "-A", "-R2", "B"))
    return f"{prefix}-{digits}{suffix}"


STYLES = [
    "verbatim", "abbrev", "wordorder", "typo", "missing_unit",
    "metric", "german", "customer_pn", "pack",
]


def render_description(row: CatalogRow, style: str, rng: random.Random) -> str:
    """Render one catalog row in the requested messy style."""
    text = row.description
    if style == "customer_pn":
        return _customer_part_number(row, rng)
    if style == "abbrev":
        return _abbreviate(text)
    if style == "wordorder":
        return _shuffle_words(text, rng)
    if style == "typo":
        return _typo(_abbreviate(text), rng)
    if style == "missing_unit":
        return _drop_units(text)
    if style == "metric":
        return _to_imperial(text, row)
    if style == "german":
        return _to_german(_abbreviate(text))
    if style == "pack":
        quantity = row.pack_size if row.pack_size > 1 else rng.choice([10, 25, 50])
        unit = "Carton" if quantity >= 50 else "Box"
        return f"{quantity} {unit} {text}"
    return text


def _gap_texts(catalog: list[CatalogRow], rng: random.Random, count: int) -> list[str]:
    """
    Build descriptions for items that do NOT exist in the catalog.

    Every gap must be absent on every attribute that matters, so a correct
    matcher can never find a legitimate SKU for it.
    """
    gap_templates = [
        "Hex Bolt M16 x 100 Grade 12.9 Black Oxide",
        "Deep Groove Ball Bearing 6902-2RS1",
        "Ball Valve 3\" Bronze 125# Threaded",
        "Stainless Elbow 4\" Schedule 80",
        "Hex Nut M20 Zinc",
        "Flat Washer 1-1/2 Stainless",
        "Zinc Plated Wing Screw 1/4-20 x 1.5",
        "Taper Lock Bushing 2517",
        "Grooved Coupling 6\" Ductile Iron",
        "Hex Bolt 7/16-14 x 6 Zinc",
        "Thrust Bearing 51105",
        "Check Valve 2\" Brass Swing",
        "Carriage Bolt 3/8-16 x 4 Zinc",
        "Anchor Bolt M16 x 180 Hot Dip Galv",
        "Set Screw M8 x 20 Cup Point",
        "Pipe Nipple 1/2\" Black 4\" Long",
        "Hex Bolt M20x100 12.9 Black",
        "Deep Groove Ball Bearing 6309-2Z",
        "Gate Valve 3\" Bronze 125#",
        "Steel Tee 3\" Schedule 80",
        "Hex Nut 7/16-28 Zinc",
        "Flat Washer M20 Stainless",
        "Roller Bearing NU205 ECP",
        "Ball Valve 4\" Stainless 600#",
        "Hex Bolt 1\"-8 x 4 Grade 8",
        "Hex Bolt M16 x 100 Grade 12.9 Black Oxide",
        "Hydraulic Fitting JIC 3/4-16 x 1-1/16",
        "Hex Bolt 9/16-12 x 5 Zinc Grade 5",
        "Deep Groove Ball Bearing 6009-2RS",
        "Ball Valve 1/2\" PVC 150#",
        "Elbow 90 4\" Schedule 80 Stainless",
        "Hex Nut M14 Zinc",
        "Flat Washer 7/16 Zinc Yellow",
        "Worm Gear Hose Clamp 3/4 Range A",
        "Globe Valve 4\" Carbon Steel 600#",
        "Hex Bolt M14 x 60 8.8 Zinc",
        "Deep Groove Ball Bearing 6307-ZZ",
        "Steel Coupling 2-1/2\" Schedule 80",
    ]
    rng.shuffle(gap_templates)
    if count > len(gap_templates):
        raise SystemExit(f"need {count} gap texts but only {len(gap_templates)} defined")
    return gap_templates[:count]


def build_rows(catalog: list[CatalogRow], split: str, count: int,
               rng: random.Random) -> list[PoRow]:
    """Build labeled rows: ~15% true gaps, the rest matched at a known style."""
    gap_count = round(count * GAP_FRACTION)
    rows: list[PoRow] = []
    index = 0

    for gap_text in _gap_texts(catalog, rng, gap_count):
        rows.append(PoRow(
            id=f"{split}-{index:03d}", text=gap_text, expected_sku="", is_gap=True,
            category="gap", style="gap", split=split,
        ))
        index += 1

    # Guarantee coverage: every style and every category appears in this split.
    need_styles = list(STYLES)
    while len(rows) < count:
        style = need_styles.pop(0) if need_styles else rng.choice(STYLES)
        row = rng.choice(catalog)
        text = render_description(row, style, rng)

        # Pack traps: a carton of 50 against a catalog stocked in eaches.
        po_uom, qty, base = "", 0.0, 0.0
        if style == "pack":
            po_uom = "Carton" if row.pack_size >= 50 else "Box"
            qty = rng.choice([1.0, 2.0, 4.0])
            base = qty * row.pack_size

        rows.append(PoRow(
            id=f"{split}-{index:03d}", text=text,
            expected_sku=row.sku, is_gap=False,
            category=row.category, style=style, split=split,
            po_uom=po_uom, po_quantity=qty, expected_base_qty=base,
            source_sku=row.sku,
            meta={"lang": row.lang, "catalog_uom": row.uom,
                  "catalog_pack": row.pack_size},
        ))
        index += 1

    # Stable ids after shuffling so the CSV diff is reviewable.
    rng.shuffle(rows)
    for position, row in enumerate(rows):
        row.id = f"{split}-{position:03d}"
    if len(rows) != count:
        raise SystemExit(f"expected {count} rows for {split}, built {len(rows)}")
    return rows


# --- persistence ------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_of(path: Path) -> str:
    """Stable hash used to freeze the test split."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Generate the catalog, both splits, and freeze the test hash."""
    rng = random.Random(SEED)
    catalog = build_catalog()
    _write_csv(DATA / "catalog.csv", [asdict(r) for r in catalog],
               list(CatalogRow.__dataclass_fields__))

    dev = build_rows(catalog, "dev", DEV_COUNT, rng)
    test = build_rows(catalog, "test", TEST_COUNT, rng)
    fields = list(PoRow.__dataclass_fields__)
    _write_csv(DATA / "dev.csv", [asdict(r) for r in dev], fields)
    test_path = DATA / "test.csv"
    _write_csv(test_path, [asdict(r) for r in test], fields)

    manifest = {
        "seed": SEED,
        "synthetic": True,
        "catalog_skus": len(catalog),
        "dev_rows": len(dev),
        "test_rows": len(test),
        "gap_fraction": GAP_FRACTION,
        "test_sha256": sha256_of(test_path),
        "dev_sha256": sha256_of(DATA / "dev.csv"),
        "styles": STYLES,
        "note": ("test.csv is FROZEN. Never edit it after matchers are built. "
                 "All data is synthetic."),
    }
    (DATA / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"catalog: {len(catalog)} SKUs")
    print(f"dev:     {len(dev)} rows  ({sum(r.is_gap for r in dev)} gaps)")
    print(f"test:    {len(test)} rows ({sum(r.is_gap for r in test)} gaps)")
    print(f"test sha256: {manifest['test_sha256']}")


if __name__ == "__main__":
    main()
