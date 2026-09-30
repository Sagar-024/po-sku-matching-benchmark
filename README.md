# PO → SKU Matching Benchmark

I tested 3 matching strategies on 200 frozen purchase-order lines against a 275-SKU industrial catalog (fasteners, bearings, valves, fittings).

| Approach | Top-1 | False match | Review rate |
|---|---:|---:|---:|
| A — Fuzzy baseline (text similarity only) | 64.5% | 11.0% | 29.0% |
| B — Attribute + LLM (extract → score attributes → abstain when uncertain) | 78.5% | **2.0%** | 12.0% |
| C — Hybrid (attributes + fuzzy tiebreaker) | **82.0%** | 6.0% | 0.0% |

### Key finding

**The highest Top-1 score was not the safest system.**

The hybrid (C) reached 82.0% Top-1, but its false-match rate was 3× higher than the attribute-based approach (B): 6.0% vs 2.0%. C's fuzzy tiebreak auto-resolves exactly the cases B would safely send to review — its 0.0% review rate is every ambiguity pushed to a coin flip. For an ERP/ordering workflow, **knowing when not to auto-match was as important as improving Top-1 accuracy**.

**→ Start with the results: [`RESULTS.md`](RESULTS.md)**

> All data is synthetic. These results demonstrate methodology, not production performance. Full limitations [below](#honest-limitations).

[Run the benchmark](#reproduce-the-numbers) · [View failures](results/test_failures.md) · [View methodology](#protocol)

## Why this benchmark exists

I built this after thinking about a specific onboarding problem: before deploying an automated purchasing workflow, how do we know that messy customer PO lines can be mapped safely to the catalog? The benchmark focuses on that matching boundary: when should the system auto-match, when should it abstain, and when is the input fundamentally unresolvable without additional customer data?

## Pipeline

```text
PO text
  ↓
LLM attribute extraction        (probabilistic, batched, disk-cached)
  ↓
Normalization                   (deterministic: fractions, threads, finishes)
  ↓
Candidate matching              (deterministic)
  ↓
Attribute scoring               (deterministic)
  ↓
Confidence / review decision    (deterministic)
  ↓
Output: SKU / REVIEW / GAP
```

The three matchers differ in the last two stages:

- **A — Fuzzy baseline.** Text similarity only.
- **B — Attribute matcher.** Extract structured attributes → compare attributes → abstain when uncertain.
- **C — Hybrid.** Attribute matching + fuzzy tiebreaker (auto-resolves what B would review).

## Start here

1. **Results** → [`RESULTS.md`](RESULTS.md)
2. **Failure analysis** → [`results/test_failures.md`](results/test_failures.md)
3. **Methodology** → [Protocol](#protocol)
4. **Code** → [`matchers.py`](matchers.py)

## Results — frozen test split

200 rows, 275-SKU catalog, one LLM extraction run (10 batches, 0 fallbacks).
Model `space-bunny-free` via OpenCode Zen, temperature 0 — a **free-tier model,
whose name may change or disappear**. The raw extraction responses are committed
in `cache/` for exactly that reason, so these numbers stay reproducible offline
even if the endpoint or model is retired. Test set SHA256
`3ccceeae8f9a2bb19538f6f7c95ba9ebaff0a94a5a5ab855c14fa0216e34cf69`.

| Matcher | Top-1 | False-match | Gap recall | Gap precision | Review rate | Auto rate |
|---|---|---|---|---|---|---|
| A baseline (fuzzy) | 64.5% | 11.0% | 40.0% | 27.9% | 29.0% | 49.5% |
| B attribute + LLM | 78.5% | **2.0%** | 90.0% | 52.9% | 12.0% | 62.5% |
| C hybrid | **82.0%** | 6.0% | 90.0% | 52.9% | 0.0% | 74.5% |

UoM pack-size accuracy: **21.7%** on the 23 rows that state a pack unit.
Cost of the frozen run: **10 LLM calls, 68,449 tokens, 0 fallbacks**. The ~17 min
is the *sum* of the individual call times (the harness records per-call seconds
and adds them up), not elapsed time; with 8 concurrent workers, real wall-clock
was shorter.

### Test failures — C hybrid (36 of 200)

| cause | count | share |
|---|---|---|
| catalog item reported as a gap (matcher gave up) | 24 | 66.7% |
| wrong SKU auto-matched or true gap force-matched | 12 | 33.3% |

Where they cluster:

- **`customer_pn`: 0/20.** Lines that are a bare customer part number (e.g.
  `PN-84368B`) share no token with any description. This is a cross-reference
  problem, not a matching problem; no text matcher can solve it.
- **Pressure/rating confused with length** in fittings: a `150#`/`125#` rating
  misread as a length.
- **Finish near-miss:** `Zinc Yellow` auto-matched to `Zinc`.
- **Typos** (`Hx Blt 7/1-614`, `DGBB 2601-2Z`) are split between recovered and missed.

Full per-row list: `results/test_failures.md`.

---

## Reproduce the numbers

One command, from the repo root — **no API key and no network required**:

```bash
git clone https://github.com/Sagar-024/po-sku-matching-benchmark
cd po-sku-matching-benchmark
pip install -r requirements.txt
python run_eval.py --split test
```

The committed LLM responses in `cache/` are keyed by prompt + batch, so this run
replays them and prints `cache_hits=10, llm_calls=0`. This is also what makes the
result survive the free-tier model being renamed or retired. The harness
re-checks `data/test.csv` against its SHA256 in `data/manifest.json` **before**
scoring, so a silently edited test set cannot produce a flattering number. To
re-extract from scratch (cache miss) instead, copy `.env.example` to `.env`, set
`LLM_API_KEY`, and run the same command.

Setup and tests:

```bash
python -m pip install -r requirements.txt
python -m pytest tests -q
```

---

## Protocol

The test set was generated and hashed before any matcher was written, and it has
never been edited afterwards. **This repo was split out of the original project as
a single fresh commit, so the commit history here cannot show that ordering.**
What this repo *can* verify, on every run, is that the hash is recorded in
`data/manifest.json` and re-checked before scoring — both by `run_eval.py` and by
`tests/test_benchmark.py`.

**Did matcher code change after the results were first seen?** No. `matchers.py`,
`normalize.py`, `uom.py` and `metrics.py` are byte-identical to the versions that
produced the committed results, and no commit after the results touched them. The
check that matters is mechanical, not historical: replaying the committed cached
responses through the committed code reproduces `results/test_*.csv` exactly, so
the code, the cache and the numbers in this repo agree with one another. The only
post-run changes were documentation, plus — when the repo was split out — import
paths, docstrings, and the vendoring of the two small support modules.

| | |
|---|---|
| Catalog | 275 SKUs, structured attributes |
| Dev split | 100 rows, **tuning allowed** |
| Test split | 200 rows, **frozen**, 15% true gaps |
| Test SHA256 | `3ccceeae8f9a2bb19538f6f7c95ba9ebaff0a94a5a5ab855c14fa0216e34cf69` |
| Seed | `20260930` |

### Rules

1. Tune **only** on `data/dev.csv`.
2. Never edit `data/test.csv` after seeing a test result.
3. If a bug forces a dataset fix, re-freeze and **report both runs**.
4. If a result is bad, report it as is.
5. Labels come from the generator's source record, never from a matcher.

`validate_dataset.py` re-checks the split integrity, including that the hash on
disk still matches `data/manifest.json`.

## Dataset

**Catalog.** 275 SKUs across `fastener`, `bearing`, `valve`, `fitting`, with
explicit `size`, `thread`, `length`, `material`, `finish`, `grade`, `uom`,
`pack_size` columns and ASME/ISO/DIN naming. Deliberate hard negatives:

- thread pitch: `3/8-16` vs `3/8-24`, `1/2-13` vs `1/2-20`
- finish: `Zinc` vs `Zinc Yellow`
- grade: `Grade 5` vs `Grade 8`
- bearing: `6203-2RS` vs `6203-2Z` vs `6203-ZZ`

**PO styles.** `verbatim`, `abbrev`, `wordorder`, `typo`, `missing_unit`,
`metric`, `german` (e.g. *Sechskantschraube M10x40 verzinkt*), `customer_pn`
(numbers sharing no words with our catalog), `pack` (Carton/Box quantity traps),
plus `gap` for items that legitimately do not exist.

## Honest limitations

- **Synthetic, self-authored data.** Descriptions were generated from templates,
  not taken from a real distributor. The 64.5% fuzzy baseline in particular
  flatters the incumbent: real customer wording is harder than these templates.
- **Small catalog (275 SKUs).** A real catalog is tens of thousands of rows; at
  50k the O(items × catalog) loop in A and B is the first thing to fall over.
- **No production traffic.** No OCR, no scanned PDFs, no multi-page documents.
- **Weak, narrow UoM result.** 21.7% on 23 rows; the conversion table covers only
  a handful of pack units and the sample is too small to trust.
- **One run, one model, temperature 0.** No variance estimate; a different model
  or a re-run could move these numbers.
- **One batch size (20) and one prompt** for extraction; either could change B/C.
- **`customer_pn` rows are unscoreable by design.** 0/20 is a property of the
  dataset (a bare customer part number shares no token with any description), not
  a fixable matcher bug.

## What this does NOT prove

- That these numbers transfer to a real catalog or real purchase orders.
- That the matcher is production-ready at catalog scale or under OCR noise.
- That Comena's actual catalog behaves like the hard negatives imagined here
  (`3/8-16` vs `3/8-24`, `Zinc` vs `Zinc Yellow`, `Grade 5` vs `Grade 8`,
  `6203-2RS` vs `6203-2Z` vs `6203-ZZ`).
- Anything about matching accuracy on customer part-number cross-references.

## Layout

```
run_eval.py          # score every matcher, write results/ and the failure list
run_dev.py           # same, on the dev split (tuning only)
matchers.py          # A baseline fuzzy, B attribute, C hybrid
metrics.py           # top-1 / false-match / gap recall+precision / review+auto
normalize.py         # fractions, metric sizes, thread, finish/material/grade/bearing
uom.py               # pack-size factor table and conversions
llm_extract.py       # batched, concurrent, disk-cached attribute extraction
extractor/           # vendored: rule fallback + endpoint settings (no key needed on cache hit)
generate_dataset.py  # deterministic synthetic generator (seed 20260930)
validate_dataset.py  # dataset integrity checks, incl. the frozen hash
data/                # catalog.csv, dev.csv, test.csv (frozen), manifest.json
cache/               # committed LLM extraction responses (offline replay)
results/             # committed per-row results, summary and full failure list
tests/               # offline, deterministic invariant tests
```

## Reproduction metadata

| | |
|---|---|
| Test SHA256 | `3ccceeae8f9a2bb19538f6f7c95ba9ebaff0a94a5a5ab855c14fa0216e34cf69` |
| Rows / catalog | 200 / 275 |
| LLM calls / tokens | 10 / 68,449 |
| Fallbacks | 0 |
| Model | `space-bunny-free` (OpenCode Zen free tier; name may change — see `cache/`) |
| Prompt | compact JSON schema, short keys, 8 attributes |
| max_tokens | 16384 |

A dev-only speed test of a 3000-token budget truncated the model's JSON
mid-string (reasoning tokens consume the budget), so the safe 16384 budget was
kept. Prompt changes were measured on dev batch 0 **before** freezing: compact
top-1 was equal-or-better (B 80% vs 75%), so it was kept. The model was never
changed — only the prompt/schema was compacted.
