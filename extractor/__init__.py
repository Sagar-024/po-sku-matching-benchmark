"""Small support modules the benchmark needs, vendored so it runs standalone.

`attribute_extractor` is the deterministic rule extractor used ONLY as a
fallback when the LLM is unavailable (it is counted and reported, never hidden).
`settings` reads an OpenAI-compatible endpoint config from the environment or a
local `.env`; it is touched ONLY on a cache miss, so a cached run needs no key.
"""
