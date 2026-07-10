# CLAUDE.md

Instructions for any AI agent (Claude Code or otherwise) working in this repo. Read this
first. For depth, see [ARCHITECTURE.md](ARCHITECTURE.md) (how the system works),
[BUILD_ROADMAP.md](BUILD_ROADMAP.md) (what's planned/being implemented), [PROGRESS.md](PROGRESS.md)
(current state at a glance), and [STATUS.md](STATUS.md) (detailed chronological build log).

## What this is

Techna is a **deterministic technical-analysis agent** for stocks. It reports indicator
*states* ("RSI = 72, overbought"), never advice. See [README.md](README.md) for the full
feature list and usage.

## The five rules that must never be broken

1. **No LLM computes a number.** Every value comes from a pure `compute_x(series, ...) ->
   result` function, tested against a hand-derived golden fixture. If you catch yourself
   about to have an LLM estimate/guess a financial number, stop — write a deterministic
   function instead.
2. **No advice language.** "buy", "sell", "hold", "recommend" (as whole words) are forbidden
   in every user-facing string. `report_builder.assert_no_advice()` enforces this at runtime
   on every `finding` sentence and event `detail` — call it on any new prose you add.
3. **Config is the single source of truth.** A threshold or window size must exist in
   `techna/config.py` in exactly one place. Never hardcode a literal that duplicates a config
   value elsewhere — a full audit this session (see STATUS.md, "Korelasyon denetimi") found
   and fixed 7 real bugs caused by exactly this pattern (e.g. an event detector comparing
   against a hardcoded `70` while the actual RSI threshold had moved in config).
4. **Golden-fixture tests never mirror the code they test.** A test that calls the same
   code path and freezes whatever it outputs proves nothing. Reference values must be
   hand-derived, or cross-checked against an independent library/source.
5. **Never trust "tests pass" as the end of verification.** Read the actual code, run it
   live against a real ticker, and look at the output. Every real bug found in this project
   was found this way, not by the test suite going red.

## Non-obvious gotchas

- **`mypy` needs two separate passes.** `techna.py` (the CLI script) and `techna/` (the
  package) share a name, so mypy cannot scan both in one invocation:
  `python -m mypy techna && python -m mypy techna.py`. Both must stay clean.
- **Console output must stay ASCII-only** outside `rich` panel borders. Fancy unicode
  (arrows, em-dashes in plain `print()`) has crashed on Windows cp1254 codepages in the past.
- **Partial time periods are never reported as full periods.** Seasonality excludes the
  current partial month; the same discipline applies to any new resampling code (weekly,
  quarterly, ...).
- **Look-ahead is a recurring bug class.** Rolling windows (Donchian, 52-week range, anchored
  VWAP) must exclude the current bar unless explicitly intended otherwise — verified via
  `shift(1)` and a dedicated no-look-ahead test.
- **Notebook content must be live-sourced, never hand-typed.** Source code, docstrings, and
  parameter tables shown in `{TICKER}_report.ipynb` are fetched via `inspect.getsource()` /
  `inspect.getdoc()` at generation time — this is how they can never drift from the real code.
  Follow the same pattern for any new notebook content.

## Commands

```bash
python -m pytest                          # 236 offline tests, ~90s, no network
python -m ruff check techna/ tools/ techna.py tests/
python -m mypy techna && python -m mypy techna.py
python techna.py AAPL --no-interactive     # live end-to-end check on a real ticker
python tools/verify_deps.py                # slopsquatting check before adding a dependency
```

## Adding a new indicator module — checklist

(See [ARCHITECTURE.md](ARCHITECTURE.md#adding-a-new-module) for the full walkthrough.) In
short: pure `compute_x()` in `techna/indicators/`, golden-fixture tests, a `*_finding()`
function in `report_builder.py` guarded by `assert_no_advice()`, wired into `techna.py`'s
`io_contract.make_result(...)` call with raw metrics (not just state), added to
`render_report_notebook()`'s `module_mapping`, a chart-fidelity test if it draws a chart, and
an entry in README's indicator table.

## Scope boundaries (permanent)

Techna is the **technical-analysis** program in a planned three-program suite. Do not add:
- **Fundalyzer's** territory: fundamental analysis (P/E, DCF, balance sheets, peer comparison).
- **Vartex's** territory: risk quantification (VaR/CVaR, GARCH, Sharpe/Sortino/Calmar).

## Workflow used to build this

This project was built through a two-role loop: an architect/reviewer role (writes Gherkin
specs and phased implementation instructions in `BUILD_ROADMAP.md`) and an implementing
agent, followed by **independent verification** of every phase — reading the code, running it
live, never trusting a green test suite alone. If you're continuing this project, keep that
loop: plan → implement → verify independently → log in `STATUS.md`.
