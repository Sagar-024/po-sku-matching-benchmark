# Results — PO → SKU Matching Benchmark

### I tested 3 matching strategies on 200 frozen PO lines against a 275-SKU catalog.

200 frozen test rows · 275-SKU catalog · 15% true gaps · one LLM extraction run (10 calls, 68,449 tokens, 0 fallbacks). Test set SHA256 `3ccceeae8f9a2bb19538f6f7c95ba9ebaff0a94a5a5ab855c14fa0216e34cf69`.

| Approach | Top-1 | False match | Gap recall | Gap precision | Review rate | Auto rate |
|---|---:|---:|---:|---:|---:|---:|
| A — Fuzzy baseline (text similarity only) | 64.5% | 11.0% | 40.0% | 27.9% | 29.0% | 49.5% |
| B — Attribute + LLM (extract structured attributes → score → abstain when uncertain) | 78.5% | **2.0%** | 90.0% | 52.9% | 12.0% | 62.5% |
| C — Hybrid (attributes + fuzzy tiebreaker) | **82.0%** | 6.0% | 90.0% | 52.9% | 0.0% | 74.5% |

## The important tradeoff

**The highest Top-1 score was not the safest system.**

Hybrid (C) improves Top-1 from **78.5% → 82.0%** over the attribute matcher (B), but its false-match rate is **3× higher (6.0% vs 2.0%)**. The reason is structural: C's fuzzy tiebreak auto-resolves exactly the cases B would safely send to review. C's 0.0% review rate is not a win — it is every ambiguity pushed to a coin flip.

In an ERP/ordering workflow a false match means the wrong part ships. If a wrong SKU costs more than a review, **B is the safer matcher**, and the Top-1 gap is only 3.5 points.

> The system that matches more often is also more willing to make a wrong decision instead of asking for review.

## What surprised me

- **Some failures are not matching failures at all.** Bare customer part numbers (`PN-84368B`, `SKU-43390-R2`) share no token with any catalog description: 0/20. That is a cross-reference-data problem, not a text-matching problem — no matcher can solve it.
- **Most of the dangerous errors are pack-size confusion.** Nearly every wrong auto-match is "expected pack of 50, matched pack of 1" — the UoM result (21.7% accurate on the 23 rows that state a pack unit) is the weakest link.
- **The fuzzy tiebreaker is the source of the harm.** Of C's 12 wrong matches, most are the fuzzy tiebreak resolving 2-way ties toward the wrong pack size; B would have reviewed those rows instead.
- **The gap side flipped completely.** A misses 60% of true gaps (gap recall 40%); B and C catch 90%. Abstaining correctly is where the attribute approach earns most of its value.

## What failed (C hybrid — 36 of 200 rows)

| Failure mode | Count | Share | What it tells us |
|---|---:|---:|---|
| Catalog item reported as a gap (matcher gave up) | 24 | 66.7% | Retrieval / candidate-generation issue — includes all 20 `customer_pn` rows, which are unscoreable by design |
| True gap force-matched into the catalog | 3 | 8.3% | Abstain-threshold calibration |
| Wrong SKU auto-matched (mostly pack-size ties) | 9 | 25.0% | Auto-match safety issue; needs proper pack-size handling |

Where they cluster:

- **`customer_pn`: 0/20.** A bare customer part number shares no token with any description. Cross-reference table required.
- **Pressure/rating confused with length** in fittings: a `150#`/`125#` rating misread as a length.
- **Finish near-miss:** `Zinc Yellow` auto-matched to `Zinc`.
- **Typos** (`Hx Blt 7/1-614`, `DGBB 2601-2Z`) split between recovered and missed.

Full per-row list, nothing filtered: [`results/test_failures.md`](results/test_failures.md).

## Reproduce

One command, from the repo root — **no API key and no network required**:

```bash
git clone https://github.com/Sagar-024/po-sku-matching-benchmark
cd po-sku-matching-benchmark
pip install -r requirements.txt
python run_eval.py --split test
```

The committed LLM responses in `cache/` are replayed offline (prints `cache_hits=10, llm_calls=0`), and the harness re-checks the test-set hash before scoring.

*All data is synthetic. These results demonstrate methodology, not production performance — see the limitations in the [README](README.md#honest-limitations).*
