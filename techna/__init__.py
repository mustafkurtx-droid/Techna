"""Techna — a deterministic technical-analysis agent for stocks.

Core rule: numbers are NEVER produced by an LLM. Every value is computed
by verifiable Python (pandas/numpy) and unit-tested against frozen golden
fixtures. This package only orchestrates and reports indicator *states* —
it gives no buy/sell advice.

Phase 0 contents:
    config        - paths, schema, defaults (no math)
    data_layer    - single cached OHLCV source (fetch once, reuse)
    io_contract   - the shared result-dict contract every module returns
    security      - dependency provenance / slopsquatting defense

Indicators (SMA, RSI, MACD, ...) are intentionally absent until Phase 1.
"""

__version__ = "0.0.0"
