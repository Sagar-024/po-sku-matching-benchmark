# Failure analysis — C_hybrid on `test`

Split: `test` | rows: 200 | failures: **36**

Every failure is listed. Nothing is filtered or dropped.
ALL DATA IS SYNTHETIC.

## By cause

| cause | count | share of failures |
|---|---|---|
| catalog item reported as a gap (matcher gave up) | 24 | 66.7% |
| true gap force-matched into the catalog | 3 | 8.3% |
| wrong SKU auto-matched (expected FT-Elbow 90-12-Carbon Steel-10, got FT-Elbow 90-12-Carbon Steel-1) | 2 | 5.6% |
| wrong SKU auto-matched (expected FT-Elbow 90-112-Stainless Steel-50, got FT-Elbow 90-112-Stainless Steel-1) | 2 | 5.6% |
| wrong SKU auto-matched (expected HB-12-13-15-Grade 5-Zinc Yellow, got HB-12-13-15-Grade 5-Zinc) | 1 | 2.8% |
| wrong SKU auto-matched (expected FT-Elbow 90-2-Brass-50, got FT-Elbow 90-2-Brass-1) | 1 | 2.8% |
| wrong SKU auto-matched (expected FT-Reducer-38-Stainless Steel-50, got FT-Reducer-38-Stainless Steel-1) | 1 | 2.8% |
| wrong SKU auto-matched (expected FT-Coupling-2-Brass-50, got FT-Coupling-2-Brass-1) | 1 | 2.8% |
| wrong SKU auto-matched (expected FT-Elbow 90-38-Stainless Steel-50, got FT-Elbow 90-38-Stainless Steel-1) | 1 | 2.8% |

## catalog item reported as a gap (matcher gave up) (24)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| test-003 | typo | `Hx Blt 7/1-614  x2.5" Gr5 Plain` | HB-716-14-25-Grade 5-Plain | — | every candidate conflicted |
| test-012 | customer_pn | `PN-84368B` | HB-38-24-2-Grade 5-Zinc Yellow | — | no attributes extracted |
| test-018 | customer_pn | `PN-81237B` | HBM-M12-35-A270 | — | no attributes extracted |
| test-031 | customer_pn | `PN-60282` | HB-34-10-4-Grade 5-Zinc Yellow | — | no attributes extracted |
| test-034 | customer_pn | `INT-56170B` | HB-38-24-3-Grade 5-Zinc | — | no attributes extracted |
| test-035 | customer_pn | `INT-98478-A` | BRG-6302-2Z | — | no attributes extracted |
| test-039 | customer_pn | `INT-67136-A` | FT-Elbow 90-38-Carbon Steel-50 | — | no attributes extracted |
| test-051 | typo | `DGB B6200-2Z` | BRG-6200-2Z | — | below review floor |
| test-060 | customer_pn | `PN-98972-A` | GV-34-Stainless Steel-300 | — | no attributes extracted |
| test-064 | customer_pn | `CUST-38554` | GV-114-Stainless Steel-200 | — | no attributes extracted |
| test-075 | customer_pn | `SKU-94887-R2` | FT-Coupling-2-Brass-50 | — | no attributes extracted |
| test-082 | customer_pn | `SKU-43390` | BRG-6200-ZZ | — | no attributes extracted |
| test-084 | customer_pn | `SKU-39542-R2` | FT-Tee-34-PVC-1 | — | no attributes extracted |
| test-102 | customer_pn | `SKU-54930-R2` | SHCS-M8-80-109 | — | no attributes extracted |
| test-110 | customer_pn | `SKU-59868-R2` | HBM-M10-50-109 | — | no attributes extracted |
| test-122 | customer_pn | `CUST-57197` | HB-14-20-075-Grade 5-Plain | — | no attributes extracted |
| test-147 | metric | `Setzkopfschraube 6mm x 40mm 10.9 DIN 912` | SHCS-M6-40-109 | — | every candidate conflicted |
| test-151 | customer_pn | `PN-79701-A` | BRG-6301-2Z | — | no attributes extracted |
| test-154 | customer_pn | `PN-39608` | BRG-6301-ZZ | — | no attributes extracted |
| test-158 | customer_pn | `CUST-80597-R2` | SHCS-M12-50-88 | — | no attributes extracted |
| test-175 | customer_pn | `PN-96107-A` | GV-18-Brass-300 | — | no attributes extracted |
| test-190 | customer_pn | `CUST-96851-A` | HBM-M12-35-A270 | — | no attributes extracted |
| test-194 | customer_pn | `INT-39338` | GV-114-Stainless Steel-200 | — | no attributes extracted |
| test-197 | typo | `DGBB 2601-2Z` | BRG-6201-2Z | — | every candidate conflicted |

## true gap force-matched into the catalog (3)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| test-048 | gap | `Pipe Nipple 1/2" Black 4" Long` | (gap) | FT-Coupling-12-Brass-1 | fuzzy broke 33-way tie |
| test-097 | gap | `Worm Gear Hose Clamp 3/4 Range A` | (gap) | HB-34-10-35-Grade 5-Plain | fuzzy broke 20-way tie |
| test-148 | gap | `Set Screw M8 x 20 Cup Point` | (gap) | HBM-M8-20-A270 | attributes agree 70 |

## wrong SKU auto-matched (expected FT-Elbow 90-12-Carbon Steel-10, got FT-Elbow 90-12-Carbon Steel-1) (2)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| test-022 | pack | `10 Box Carbon Steel Elbow 90 1/2" Sch 40` | FT-Elbow 90-12-Carbon Steel-10 | FT-Elbow 90-12-Carbon Steel-1 | fuzzy broke 2-way tie |
| test-162 | wordorder | `Carbon Sch Steel 90 Elbow 40 1/2"` | FT-Elbow 90-12-Carbon Steel-10 | FT-Elbow 90-12-Carbon Steel-1 | fuzzy broke 2-way tie |

## wrong SKU auto-matched (expected FT-Elbow 90-112-Stainless Steel-50, got FT-Elbow 90-112-Stainless Steel-1) (2)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| test-149 | pack | `50 Carton Stainless Steel Elbow 90 1-1/2" Sch 40` | FT-Elbow 90-112-Stainless Steel-50 | FT-Elbow 90-112-Stainless Steel-1 | fuzzy broke 2-way tie |
| test-153 | german | `SS Elb90 1-1/2" Sch 40` | FT-Elbow 90-112-Stainless Steel-50 | FT-Elbow 90-112-Stainless Steel-1 | fuzzy broke 2-way tie |

## wrong SKU auto-matched (expected HB-12-13-15-Grade 5-Zinc Yellow, got HB-12-13-15-Grade 5-Zinc) (1)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| test-040 | wordorder | `Hex Grade 5 Zinc 1/2-13 Bolt Yellow x 1.5" Head Hex` | HB-12-13-15-Grade 5-Zinc Yellow | HB-12-13-15-Grade 5-Zinc | attributes agree 135 |

## wrong SKU auto-matched (expected FT-Elbow 90-2-Brass-50, got FT-Elbow 90-2-Brass-1) (1)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| test-044 | typo | `Brass Elb90 "2 Sch 40` | FT-Elbow 90-2-Brass-50 | FT-Elbow 90-2-Brass-1 | fuzzy broke 2-way tie |

## wrong SKU auto-matched (expected FT-Reducer-38-Stainless Steel-50, got FT-Reducer-38-Stainless Steel-1) (1)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| test-126 | abbrev | `SS Rdc 3/8" Sch 40` | FT-Reducer-38-Stainless Steel-50 | FT-Reducer-38-Stainless Steel-1 | fuzzy broke 2-way tie |

## wrong SKU auto-matched (expected FT-Coupling-2-Brass-50, got FT-Coupling-2-Brass-1) (1)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| test-128 | missing_unit | `Brass Coupling 2 Sch 40` | FT-Coupling-2-Brass-50 | FT-Coupling-2-Brass-1 | fuzzy broke 2-way tie |

## wrong SKU auto-matched (expected FT-Elbow 90-38-Stainless Steel-50, got FT-Elbow 90-38-Stainless Steel-1) (1)

| id | style | text | expected | predicted | reason |
|---|---|---|---|---|---|
| test-166 | german | `SS Elb90 3/8" Sch 40` | FT-Elbow 90-38-Stainless Steel-50 | FT-Elbow 90-38-Stainless Steel-1 | fuzzy broke 2-way tie |
