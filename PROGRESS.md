# Progress

A one-page, current-state snapshot. For the detailed chronological build log (every bug found,
every fix, every verification step), see [STATUS.md](STATUS.md). For what's planned next, see
[BUILD_ROADMAP.md](BUILD_ROADMAP.md).

**Last updated:** 2026-07-05

## Status: production-ready, actively maintained

| | |
|---|---|
| Tests | 236/236 passing, offline, ~90s |
| Lint / types | `ruff` clean · `mypy` (2-pass) clean |
| Coverage | 95% (network paths + type-guards intentionally excluded) |
| CI | ![Tests](https://github.com/mustafkurtx-droid/Techna/actions/workflows/tests.yml/badge.svg) on every push to `main` |
| Modules | 19 indicator modules (20 files), 22 charts |
| Repo | [github.com/mustafkurtx-droid/Techna](https://github.com/mustafkurtx-droid/Techna) — public, Apache 2.0, `v1.0.0` released |

## What's done

All 8 planned expansion phases (BUILD_ROADMAP.md Faz 28–35) are complete and independently
verified: multi-timeframe weekly context, event detection, volume profile (daily + weekly),
Stochastic oscillator, Fibonacci retracement, Donchian channels, MFI + anchored VWAP, and
candlestick patterns. Plus two unplanned additions kept after review: Bollinger/Keltner
squeeze and weekly volume profile.

Beyond the roadmap: a "Data & Parameter Provenance" section (every report/notebook states
exactly what data and parameters produced every number), a "how this chart works" plain-English
explanation under every chart, and a full correlation audit that found and fixed 7 real bugs
where a threshold or window existed as a duplicated literal instead of a single `config.py`
constant.

## What's not done / known gaps

- No dedicated per-module I/O reference doc beyond docstrings + the README summary table
  (partially closed by `ARCHITECTURE.md`'s module inventory table).
- `techna/indicators/relative.py`'s timezone-aware-index branch in `align_close()` has no
  direct test (coverage gap, low priority — see STATUS.md's system-audit entry).
- No cross-provider validation of raw OHLCV data itself (Techna trusts yfinance as ground
  truth, same as any TA tool) — out of scope by design, not a bug.
- Report/notebook volume (22 charts, 150+ notebook cells) trades completeness for
  readability; deliberately not trimmed (see STATUS.md's scope-assessment decision — the
  reader is trusted to skip sections, not everything is meant to be read linearly).

## Scope boundaries (won't add here — see CLAUDE.md)

Fundamental analysis → Fundalyzer (separate, future program). Risk quantification (VaR/CVaR,
GARCH, Sharpe) → Vartex (separate, future program). The three merge later; Techna stays pure
technical analysis.

## Next steps

Nothing currently queued. Candidate future work (not started, needs discussion before
picking up): a "compact mode" report toggle (core ~14 modules vs. full 19), cross-provider
data validation, richer relative.py timezone test coverage.
