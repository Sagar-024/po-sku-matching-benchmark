# Failure analysis — C_hybrid on `dev`

Split: `dev` | rows: 100 | failures: **29**

Every failure is listed. Nothing is filtered or dropped.
ALL DATA IS SYNTHETIC.

## By cause

| cause | count | share of failures |
|---|---|---|
| catalog item reported as a gap (matcher gave up) | 24 | 82.8% |
| true gap force-matched into the catalog | 2 | 6.9% |
| wrong SKU auto-matched (expected GV-34-Brass-150, got GV-34-Brass-300) | 1 | 3.4% |
| wrong SKU auto-matched (expected FT-Reducer-38-Stainless Steel-50, got FT-Reducer-38-Stainless Steel-1) | 1 | 3.4% |
| sent to review with the wrong SKU (HB-516-18-1-Grade 8-Zinc) | 1 | 3.4% |

## catalog item reported as a gap (matcher gave up) (24)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| dev-009 | customer_pn | `INT-53863` | BRG-6005-ZZ | — | no attributes extracted |
| dev-010 | customer_pn | `CUST-59129-R2` | BRG-6000-2Z | — | no attributes extracted |
| dev-014 | customer_pn | `INT-84898-A` | HB-38-16-075-Grade 8-Zinc | — | no attributes extracted |
| dev-018 | metric | `Hex Bolt 6mm x 80mm 8.8 ISO 4762 Zinc Plated` | HBM-M6-80-88 | — | every candidate conflicted |
| dev-040 | customer_pn | `SKU-84520` | FT-Elbow 90-112-Stainless Steel-50 | — | no attributes extracted |
| dev-047 | customer_pn | `INT-57476` | HBM-M8-20-A270 | — | no attributes extracted |
| dev-049 | customer_pn | `SKU-44230` | BRG-6200-ZZ | — | no attributes extracted |
| dev-050 | customer_pn | `INT-57988-A` | SHCS-M8-80-109 | — | no attributes extracted |
| dev-055 | customer_pn | `SKU-78620` | HBM-M12-16-109 | — | no attributes extracted |
| dev-056 | wordorder | `Hex Grade 1/4-20 Bolt x 5 Zinc Yellow Hex Head 1.5"` | HB-14-20-15-Grade 5-Zinc Yellow | — | every candidate conflicted |
| dev-061 | metric | `Globe Valve 1/4 Brass 125# Flanged` | GV-14-Brass-125 | — | no attributes extracted |
| dev-064 | typo | `PVC wlb90 1-1/2" Sch 40` | FT-Elbow 90-112-PVC-10 | — | below review floor |
| dev-065 | pack | `10 Box Globe Valve 1/8 Stainless Steel 200# Flanged` | GV-18-Stainless Steel-200 | — | no attributes extracted |
| dev-066 | typo | `DGBB 6202-ZZ` | BRG-6202-ZZ | — | no attributes extracted |
| dev-068 | missing_unit | `Brass Coupling 1/2 Sch 40` | FT-Coupling-12-Brass-1 | — | no attributes extracted |
| dev-069 | verbatim | `Globe Valve 1-1/2 Carbon Steel 150# Flanged` | GV-112-Carbon Steel-150 | — | below review floor |
| dev-070 | customer_pn | `INT-78608` | HB-516-18-2-Grade 8-Plain | — | no attributes extracted |
| dev-072 | missing_unit | `Hex Bolt 7/16-14 x 1.5 Grade 5 Pla Hex Head` | HB-716-14-15-Grade 5-Plain | — | below review floor |
| dev-073 | german | `Hx Blt 3/4-10 x 2.5" Gr5 verzinkt` | HB-34-10-25-Grade 5-Zinc | — | below review floor |
| dev-074 | abbrev | `Hx Blt 1/4-20 x 1.5" Gr5 Zn Yel` | HB-14-20-15-Grade 5-Zinc Yellow | — | below review floor |
| dev-075 | customer_pn | `SKU-44811` | HB-716-14-4-Grade 5-Plain | — | no attributes extracted |
| dev-079 | wordorder | `Brass Coupling 1" 40 Sch` | FT-Coupling-1-Brass-50 | — | no attributes extracted |
| dev-081 | typo | `DGBB 8600-ZZ` | BRG-6800-ZZ | — | every candidate conflicted |
| dev-084 | typo | `DGBB 600-22Z` | BRG-6002-2Z | — | every candidate conflicted |

## true gap force-matched into the catalog (2)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| dev-039 | gap | `Worm Gear Hose Clamp 3/4 Range A` | (gap) | HB-34-10-35-Grade 5-Plain | fuzzy broke 20-way tie |
| dev-076 | gap | `Zinc Plated Wing Screw 1/4-20 x 1.5` | (gap) | HB-14-20-15-Grade 5-Zinc | fuzzy broke 6-way tie |

## wrong SKU auto-matched (expected GV-34-Brass-150, got GV-34-Brass-300) (1)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| dev-025 | typo | `Globe Vlv /34 Brass 150#` | GV-34-Brass-150 | GV-34-Brass-300 | fuzzy broke 3-way tie |

## wrong SKU auto-matched (expected FT-Reducer-38-Stainless Steel-50, got FT-Reducer-38-Stainless Steel-1) (1)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| dev-046 | wordorder | `Stainless 3/8" Sch Steel Reducer 40` | FT-Reducer-38-Stainless Steel-50 | FT-Reducer-38-Stainless Steel-1 | fuzzy broke 2-way tie |

## sent to review with the wrong SKU (HB-516-18-1-Grade 8-Zinc) (1)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| dev-077 | wordorder | `Hex 5 x 1/2-20 Head Zinc Bolt Grade 4" Yellow Hex` | HB-12-20-4-Grade 5-Zinc Yellow | HB-516-18-1-Grade 8-Zinc | weak evidence 30 |
