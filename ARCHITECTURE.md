# Architecture

Technical reference for how Techna is built. For principles and rules, see
[CLAUDE.md](CLAUDE.md). For user-facing usage, see [README.md](README.md).

## Data flow

```
yfinance / cache ──▶ data_layer.get_prices() ──▶ PriceData(df, source, warnings)
                                                        │
                                                        ▼
                                    techna.py: run() orchestrates all modules
                                                        │
                     ┌──────────────────────────────────┼──────────────────────────────────┐
                     ▼                                  ▼                                  ▼
          techna/indicators/*.py            techna/scoring.py                techna/briefing.py
          (20 pure compute_x functions)      (6 dimension scores)             (rule-based synthesis,
                     │                                  │                      --explain only)
                     └──────────────────────┬───────────┘
                                             ▼
                              io_contract.make_result(...) per module
                                             │
                              ┌──────────────┼──────────────┐
                              ▼              ▼              ▼
                     write_results_json  build_report   render_report_notebook
                     ({TICKER}_result    ({TICKER}      ({TICKER}_report.ipynb)
                      .json)              _report.md +
                                           22 chart PNGs)
```

`data_layer.get_prices()` is the **only** place that touches the network or a cache file.
Every indicator module receives already-clean `pd.Series`/`pd.DataFrame` and does zero I/O —
this is what "pure function" means throughout the codebase, and it's what makes the 236-test
suite run offline in ~90 seconds.

## The I/O contract

Every module (indicator, scoring, briefing, events) returns exactly this shape, built via
`io_contract.make_result()`:

```python
{
    "module":      str,          # e.g. "risk"
    "ticker":      str,
    "status":      "ok" | "warning" | "error",
    "metrics":     dict,         # raw numbers + a "finding" prose sentence
    "report_path": str | None,
    "warnings":    list[str],
}
```

`io_contract.write_results_json()` aggregates all module results plus a `data_provenance`
block (source, date range, benchmark, requested period) into `{TICKER}_result.json`. That one
JSON file is the single source both `build_report()` (markdown) and `render_report_notebook()`
(notebook) read from — markdown and notebook never compute anything themselves, they only
format what's already in the JSON (plus a few chart-only inputs like raw `pd.Series` passed
through `context_dict` for plotting).

**Rule enforced by `metrics`**: never just a state label. `metrics` must carry the raw
number(s) that produced the `finding` sentence and the chart (e.g. `risk`'s metrics include
`beta`, `beta_n` — the sample size — not just `beta_state`). This was a real, fixed gap: see
STATUS.md's "JSON metrics genişletildi" entry.

## Module inventory (20 indicator files → 19 JSON modules + scoring)

| File | JSON module key | Draws chart(s)? |
|---|---|---|
| `trend.py` | `trend` | overview, candles |
| `mtf.py` | `mtf` | weekly |
| `momentum.py` | `momentum` | momentum (RSI+Stochastic+MACD, 3 panels) |
| `volatility.py` | `volatility` | overview (shared) |
| `squeeze.py` | `squeeze` | — |
| `levels.py` | `levels` | levels |
| `volume_profile.py` | `volume_profile` | volume_profile |
| `volume_profile_weekly.py` | `volume_profile_weekly` | volume_profile_weekly |
| `fibonacci.py` | `fibonacci` | fibonacci |
| `donchian.py` | `donchian` | donchian |
| `candles.py` | `candles` | markers on candles chart |
| `regime.py` | `context` | regime |
| `divergence.py` | (folded into `context`) | annotation only |
| `baserates.py` | (folded into markdown/notebook) | baserates |
| `relative.py` | `relative` | relative |
| `seasonality.py` | `seasonality` | seasonality |
| `volume.py` | `volume` | volume (VWAP+AVWAP+MFI+OBV) |
| `econometrics.py` | `econometrics` | correlogram, distribution, structural_breaks, hurst, quantile_beta |
| `risk_context.py` | `risk` | 52week, drawdown, beta |
| `events.py` | `events` | — (aggregates signals from all the above) |
| `scoring.py` | `scores` | — |

## Config-driven parameters (single source of truth)

Every threshold/window used more than once **must** live in `techna/config.py` and be
referenced via `config.NAME`, never duplicated as a literal. A dedicated audit (STATUS.md,
"Korelasyon denetimi") found and fixed 7 real bugs from this pattern being violated — e.g.
`find_support_resistance(prices, k=5)` used a bare `5` while `divergence.py` already used
`config.SWING_WINDOW` (=5) for the identical concept; changing one would have silently
diverged from the other.

`report_builder._PARAMETER_TABLE` reads ~40 of these constants live via `getattr(config,
name)` to render the "Data & Parameter Provenance" section in every report/notebook — this is
also the project's own regression guard: `tests/test_data_provenance.py` monkeypatches a
config value and asserts the new value shows up everywhere it should, proving the whole chain
is genuinely live-wired, not hand-typed text that happens to currently match.

## Notebook generation: proof, not just presentation

`report_builder.render_report_notebook()` builds `{TICKER}_report.ipynb` with **zero executed
code cells** — it only constructs markdown cells via `nbformat`, so generating it never
re-runs any computation (no `ipykernel`/`nbclient` dependency on the runtime path). For every
module, in order:

1. `finding` (prose, from the JSON)
2. raw metric values (pretty JSON, from the JSON)
3. the `compute_*` function's live source (`inspect.getsource()`)
4. the `draw_*_chart` function's live source (`inspect.getsource()`)
5. the chart itself, embedded as a base64 PNG data URI (never a relative file link — this is
   what makes the notebook portable as a single file)
6. a plain-English "How this chart works" cell — the `draw_*_chart` function's docstring plus
   the relevant indicator module's docstring, both via `inspect.getdoc()`

Everything in 3–6 is fetched **live at generation time**. Nothing is hand-copied text that
could drift from the real code — this is the core design invariant of the notebook feature,
and every test that touches it (`test_report_notebook.py`) asserts against the live-sourced
content, not a hardcoded string, wherever practical.

Two separate, larger notebooks (`notebooks/full_showcase.ipynb`,
`notebooks/proof_of_correctness.ipynb`) are built by standalone scripts in `tools/` and *do*
execute real code (via `nbclient` + a registered `techna-py3` kernel) — they're one-time proof
artifacts checked into the repo, not part of the per-run CLI path. See README for what each
demonstrates.

## Testing architecture

- **Golden fixtures** (`tests/fixtures/*.csv`): hand-verifiable OHLCV data with independently
  derived reference values. A test must never call the same production code path to generate
  its own "expected" value — that proves the code agrees with itself, not that it's correct.
- **Chart-data-fidelity tests** (`tests/test_chart_data_fidelity.py`): monkeypatch
  `report_builder._save` to capture the live `matplotlib.Figure` instead of writing a PNG,
  then assert the actual plotted `Line2D`/`Bar`/`AxesImage` data equals the input data
  numerically. This is what catches "chart plots the wrong column" bugs that indicator-level
  tests can't see (e.g. the 52-week chart bug found earlier in this project's history).
- **Look-ahead tests**: any rolling-window computation gets a dedicated test proving the
  current bar cannot influence its own window boundary (see `test_donchian_no_lookahead_...`).
- **Provenance/correlation tests** (`tests/test_data_provenance.py`): monkeypatch a
  `techna.config` value and assert it propagates everywhere — the project's guard against the
  config-duplication bug class described above.

## Adding a new module

1. Write the Gherkin spec in `specs/<name>.feature` first.
2. Add `compute_x()` (pure function) to a new or existing file under `techna/indicators/`.
3. Add golden-fixture tests — hand-derived values, not code-mirrored.
4. Add a `<name>_finding(...)` function to `report_builder.py`, calling `assert_no_advice()`
   on its output.
5. Wire it into `techna.py`'s `run()`: compute → `io_contract.make_result(...)` with **raw
   metrics + finding**, not just a state label.
6. If it has a chart: add `draw_<name>_chart()` to `report_builder.py` + a chart-data-fidelity
   test.
7. Add the module to `render_report_notebook()`'s `module_mapping` (finding + chart images +
   the `compute_*` function reference) — a module missing here silently loses its notebook
   representation with no error; `test_every_json_module_appears_in_the_notebook` guards this.
8. If it introduces a new threshold/window, add it to `techna/config.py` (never a local
   literal) and to `report_builder._PARAMETER_TABLE`.
9. Update the README indicator table.
10. Log the phase in `STATUS.md`; update `PROGRESS.md`'s current-state summary.

## Scope boundaries

See [CLAUDE.md](CLAUDE.md#scope-boundaries-permanent) — Techna stays pure technical analysis;
fundamental analysis and risk-quantification are separate, planned programs (Fundalyzer,
Vartex) that will merge with this one later, not features to add here.
