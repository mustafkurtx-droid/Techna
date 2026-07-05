"""Chart-data-fidelity tests.

Golden-fixture tests already prove the *indicator computations* are correct
(``compute_x(...)`` matches hand-verified values). ``proof_of_correctness.ipynb``
separately cross-checks that math against an independent library. Neither of
those proves the *charts* actually draw the numbers they were handed --
a chart function could silently plot the wrong column, a stale array, or a
misaligned index while every indicator test still passes (this happened for
real: the 52-week chart and the overview chart's pivot levels both had this
exact class of bug, found only by manual reading, not by any test).

These tests close that gap: for every ``draw_*_chart`` function, they inspect
the actual matplotlib ``Line2D``/``Bar``/``AxesImage`` objects captured on the
figure and assert their data is numerically identical to the values passed
in -- proving "what's plotted" == "what was computed", not just "the function
ran without crashing".

``_save`` (which calls ``fig.savefig`` + ``plt.close``) is monkeypatched to
capture the live ``Figure`` instead, so we can inspect the in-memory artist
data directly rather than re-parsing a PNG.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import matplotlib.pyplot as plt
import scipy.stats

from techna import report_builder as rb


@pytest.fixture
def capture_fig(monkeypatch):
    captured: dict = {}

    def fake_save(fig, out_path):
        captured["fig"] = fig

    monkeypatch.setattr(rb, "_save", fake_save)
    yield captured
    if "fig" in captured:
        plt.close(captured["fig"])


def _df(n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    rs = np.random.RandomState(7)
    close = 100 + np.cumsum(rs.normal(0, 1, n))
    openp = close + rs.normal(0, 0.3, n)
    high = np.maximum(close, openp) + rs.uniform(0, 1, n)
    low = np.minimum(close, openp) - rs.uniform(0, 1, n)
    vol = rs.randint(1000, 5000, n)
    return pd.DataFrame(
        {"Open": openp, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx
    )


def _series(idx, seed: int) -> pd.Series:
    rs = np.random.RandomState(seed)
    return pd.Series(rs.normal(0, 1, len(idx)), index=idx)


# --------------------------------------------------------------------------- #
def test_overview_chart_plots_exact_values(capture_fig):
    df = _df()
    trend_data = {"sma20": _series(df.index, 1) + 100, "sma50": _series(df.index, 2) + 100, "sma200": None}
    volatility_data = {"upper": _series(df.index, 3) + 105, "lower": _series(df.index, 4) + 95}
    levels_data = {"v2": {
        "supports": [{"price": float(df["Close"].iloc[-1]) - 5, "touches": 3}],
        "resistances": [{"price": float(df["Close"].iloc[-1]) + 5, "touches": 2}],
    }}
    rb.draw_overview_chart("TEST", df, trend_data, volatility_data, levels_data, capture_fig)
    fig = capture_fig["fig"]
    ax1 = fig.axes[0]

    close_line = next(ln for ln in ax1.lines if ln.get_label() == "Close")
    np.testing.assert_allclose(close_line.get_ydata(), df["Close"].to_numpy())

    sma20_line = next(ln for ln in ax1.lines if ln.get_label() == "SMA 20")
    np.testing.assert_allclose(sma20_line.get_ydata(), trend_data["sma20"].to_numpy())

    upper_line = next(ln for ln in ax1.lines if ln.get_label() == "Bollinger")
    np.testing.assert_allclose(upper_line.get_ydata(), volatility_data["upper"].to_numpy())

    support_line = next(ln for ln in ax1.lines if ln.get_label() == "Support (filtered)")
    assert support_line.get_ydata()[0] == pytest.approx(levels_data["v2"]["supports"][0]["price"])

    ax2 = fig.axes[1]
    np.testing.assert_allclose([p.get_height() for p in ax2.containers[0]], df["Volume"].to_numpy())


# --------------------------------------------------------------------------- #
def test_momentum_chart_plots_exact_values(capture_fig):
    df = _df()
    rsi = (_series(df.index, 5) * 10 + 50).clip(0, 100)
    macd_df = pd.DataFrame({
        "macd": _series(df.index, 6), "signal": _series(df.index, 7), "hist": _series(df.index, 8),
    })
    stoch_df = pd.DataFrame({
        "slow_k": (_series(df.index, 30) * 10 + 50).clip(0, 100),
        "slow_d": (_series(df.index, 31) * 10 + 50).clip(0, 100),
    })
    momentum_data = {"rsi": rsi, "macd": macd_df, "stochastic": stoch_df}
    rb.draw_momentum_chart("TEST", df, momentum_data, None, capture_fig)
    fig = capture_fig["fig"]
    ax1 = fig.axes[0]
    ax2 = fig.axes[1]
    ax3 = fig.axes[2]

    rsi_line = next(ln for ln in ax1.lines if ln.get_label() == "RSI (14)")
    np.testing.assert_allclose(rsi_line.get_ydata(), rsi.to_numpy())

    k_line = next(ln for ln in ax2.lines if ln.get_label() == "Stochastic %K")
    np.testing.assert_allclose(k_line.get_ydata(), stoch_df["slow_k"].to_numpy())
    d_line = next(ln for ln in ax2.lines if ln.get_label() == "Stochastic %D")
    np.testing.assert_allclose(d_line.get_ydata(), stoch_df["slow_d"].to_numpy())

    macd_line = next(ln for ln in ax3.lines if ln.get_label() == "MACD")
    np.testing.assert_allclose(macd_line.get_ydata(), macd_df["macd"].to_numpy())
    signal_line = next(ln for ln in ax3.lines if ln.get_label() == "Signal")
    np.testing.assert_allclose(signal_line.get_ydata(), macd_df["signal"].to_numpy())
    np.testing.assert_allclose([p.get_height() for p in ax3.containers[0]], macd_df["hist"].to_numpy())


# --------------------------------------------------------------------------- #
def test_regime_chart_plots_exact_values(capture_fig):
    df = _df()
    adx_df = pd.DataFrame({
        "adx": (_series(df.index, 9).abs() * 10 + 20),
        "plus_di": _series(df.index, 10).abs() * 10,
        "minus_di": _series(df.index, 11).abs() * 10,
    })
    atr = _series(df.index, 12).abs()
    context_data = {"adx": adx_df, "atr": atr}
    rb.draw_regime_chart("TEST", df, context_data, capture_fig)
    fig = capture_fig["fig"]
    ax1, ax2 = fig.axes[0], fig.axes[1]

    adx_line = next(ln for ln in ax1.lines if ln.get_label() == "ADX")
    np.testing.assert_allclose(adx_line.get_ydata(), adx_df["adx"].to_numpy())
    plus_line = next(ln for ln in ax1.lines if ln.get_label() == "+DI")
    np.testing.assert_allclose(plus_line.get_ydata(), adx_df["plus_di"].to_numpy())

    atr_line = next(ln for ln in ax2.lines if ln.get_label() == "ATR (14)")
    np.testing.assert_allclose(atr_line.get_ydata(), atr.to_numpy())


# --------------------------------------------------------------------------- #
def test_levels_chart_plots_exact_values(capture_fig):
    df = _df()
    current = float(df["Close"].iloc[-1])
    levels_v2 = {
        "supports": [{"price": current - 3, "touches": 4}],
        "resistances": [{"price": current + 3, "touches": 1}],
    }
    rb.draw_levels_chart("TEST", df, levels_v2, capture_fig)
    fig = capture_fig["fig"]
    ax = fig.axes[0]

    close_line = next(ln for ln in ax.lines if ln.get_label() == "Close Price")
    np.testing.assert_allclose(close_line.get_ydata(), df["Close"].to_numpy())

    support_line = next(ln for ln in ax.lines if ln.get_label() == "Support")
    assert support_line.get_ydata()[0] == pytest.approx(levels_v2["supports"][0]["price"])
    resistance_line = next(ln for ln in ax.lines if ln.get_label() == "Resistance")
    assert resistance_line.get_ydata()[0] == pytest.approx(levels_v2["resistances"][0]["price"])


# --------------------------------------------------------------------------- #
def test_candles_chart_plots_exact_ohlc(capture_fig):
    df = _df(40)
    n = 20
    trend_data = {"sma20": _series(df.index, 13) + 100}
    rb.draw_candles_chart("TEST", df, trend_data, capture_fig, n=n)
    fig = capture_fig["fig"]
    ax = fig.axes[0]
    sub = df.iloc[-n:]

    # Wicks: one LineCollection via ax.vlines, segments are [[x, low], [x, high]].
    wick_coll = ax.collections[0]
    segments = wick_coll.get_segments()
    plotted_low = np.array([seg[0][1] for seg in segments])
    plotted_high = np.array([seg[1][1] for seg in segments])
    np.testing.assert_allclose(plotted_low, sub["Low"].to_numpy())
    np.testing.assert_allclose(plotted_high, sub["High"].to_numpy())

    # Bodies: two bar containers (up days, down days); union of heights+bottoms
    # must reconstruct exactly {open, close} per bar (as min/max pairs).
    o = sub["Open"].to_numpy()
    c = sub["Close"].to_numpy()
    up_mask = c >= o
    expected_bottom = np.minimum(o, c)
    expected_top = np.maximum(o, c)

    up_container, down_container = ax.containers[0], ax.containers[1]
    up_bottoms = np.array([p.get_y() for p in up_container])
    up_tops = up_bottoms + np.array([p.get_height() for p in up_container])
    np.testing.assert_allclose(up_bottoms, expected_bottom[up_mask])
    np.testing.assert_allclose(up_tops, expected_top[up_mask], rtol=1e-6, atol=1e-6)

    down_bottoms = np.array([p.get_y() for p in down_container])
    down_tops = down_bottoms + np.array([p.get_height() for p in down_container])
    np.testing.assert_allclose(down_bottoms, expected_bottom[~up_mask])
    np.testing.assert_allclose(down_tops, expected_top[~up_mask], rtol=1e-6, atol=1e-6)

    sma_line = next(ln for ln in ax.lines if ln.get_label() == "SMA 20")
    np.testing.assert_allclose(sma_line.get_ydata(), trend_data["sma20"].iloc[-n:].to_numpy())


# --------------------------------------------------------------------------- #
def test_baserates_chart_marks_true_conditional_means(capture_fig):
    idx = pd.date_range("2024-01-01", periods=200, freq="B")
    fwd10 = _series(idx, 14) * 0.02
    cond_rsi = pd.Series(np.arange(200) % 5 == 0, index=idx)   # 40 True days
    cond_boll = pd.Series(np.arange(200) % 7 == 0, index=idx)  # ~29 True days

    rb.draw_baserates_chart("TEST", fwd10, cond_rsi, cond_boll, capture_fig)
    fig = capture_fig["fig"]
    ax1 = fig.axes[0]

    # Independently recompute the expected conditional mean from the SAME raw
    # inputs (not by calling report_builder's code) and check the axvline
    # position matches -- proving the annotated mean is the real subset mean.
    df_rsi = pd.DataFrame({"cond": cond_rsi, "fwd": fwd10}).dropna()
    rsi_fwd = df_rsi.loc[df_rsi["cond"], "fwd"]
    expected_mean_pct = rsi_fwd.mean() * 100

    rsi_mean_line = next(ln for ln in ax1.lines if ln.get_label().startswith("RSI Mean"))
    assert rsi_mean_line.get_xdata()[0] == pytest.approx(expected_mean_pct)


# --------------------------------------------------------------------------- #
def test_relative_chart_plots_exact_values(capture_fig):
    idx = pd.date_range("2024-01-01", periods=80, freq="B")
    asset_rebased = 100 + _series(idx, 15).cumsum()
    bench_rebased = 100 + _series(idx, 16).cumsum()
    rs = 1.0 + _series(idx, 17) * 0.01
    rs_ma = rs.rolling(5, min_periods=1).mean()

    rb.draw_relative_chart("TEST", "SPY", asset_rebased, bench_rebased, rs, rs_ma, capture_fig)
    fig = capture_fig["fig"]
    ax1, ax2 = fig.axes[0], fig.axes[1]

    asset_line = next(ln for ln in ax1.lines if ln.get_label() == "TEST (Rebased)")
    np.testing.assert_allclose(asset_line.get_ydata(), asset_rebased.to_numpy())

    rs_line = next(ln for ln in ax2.lines if ln.get_label() == "Relative Strength Ratio")
    np.testing.assert_allclose(rs_line.get_ydata(), rs.to_numpy())
    rs_ma_line = next(ln for ln in ax2.lines if ln.get_label().startswith("RS SMA"))
    np.testing.assert_allclose(rs_ma_line.get_ydata(), rs_ma.to_numpy())


# --------------------------------------------------------------------------- #
def test_seasonality_chart_imshow_matches_table_pct(capture_fig):
    years = [2022, 2023, 2024]
    rs = np.random.RandomState(18)
    table = pd.DataFrame(rs.normal(0, 0.03, (3, 12)), index=years,
                          columns=range(1, 13))
    rb.draw_seasonality_chart("TEST", table, capture_fig)
    fig = capture_fig["fig"]
    ax = fig.axes[0]
    im = ax.images[0]

    expected = np.vstack([(table * 100.0).values, (table * 100.0).mean(axis=0).values])
    np.testing.assert_allclose(im.get_array(), expected)


# --------------------------------------------------------------------------- #
def test_volume_chart_plots_exact_values(capture_fig):
    df = _df()
    vwap = _series(df.index, 19) + 100
    obv = _series(df.index, 20).cumsum()
    mfi = pd.Series([50.0] * len(df), index=df.index)
    avwap_ytd = pd.Series([99.0] * len(df), index=df.index)
    avwap_high = pd.Series([102.0] * len(df), index=df.index)
    avwap_low = pd.Series([98.0] * len(df), index=df.index)
    
    rb.draw_volume_chart("TEST", df, vwap, obv, mfi, avwap_ytd, avwap_high, avwap_low, capture_fig)
    fig = capture_fig["fig"]
    axes = fig.axes
    ax1 = axes[0]
    ax3 = axes[2]
    obv_twin = axes[3]

    close_line = next(ln for ln in ax1.lines if ln.get_label() == "TEST Close")
    np.testing.assert_allclose(close_line.get_ydata(), df["Close"].to_numpy())
    vwap_line = next(ln for ln in ax1.lines if ln.get_label() == "VWAP (20)")
    np.testing.assert_allclose(vwap_line.get_ydata(), vwap.to_numpy())

    np.testing.assert_allclose([p.get_height() for p in ax3.containers[0]], df["Volume"].to_numpy())

    obv_line = next(ln for ln in obv_twin.lines if ln.get_label() == "OBV")
    np.testing.assert_allclose(obv_line.get_ydata(), obv.to_numpy())


# --------------------------------------------------------------------------- #
def test_correlogram_chart_stems_match_acf_values(capture_fig):
    acf_pacf_data = {
        "conf": 0.1,
        "raw": {"acf": np.array([1.0, 0.2, -0.05, 0.1])},
        "abs": {"acf": np.array([1.0, 0.3, 0.15, 0.05])},
        "sq": {"acf": np.array([1.0, 0.25, 0.1, 0.02])},
    }
    rb.draw_correlogram_chart("TEST", acf_pacf_data, capture_fig)
    fig = capture_fig["fig"]
    ax1 = fig.axes[0]
    markerline = ax1.containers[0].markerline
    np.testing.assert_allclose(markerline.get_ydata(), acf_pacf_data["raw"]["acf"])


# --------------------------------------------------------------------------- #
def test_distribution_chart_fitted_curves_use_passed_params(capture_fig):
    rs = np.random.RandomState(21)
    returns = pd.Series(rs.normal(0, 0.02, 300))
    dist_data = {
        "normal_fit": {"loc": 0.001, "scale": 0.02},
        "t_fit": {"df": 5.0, "loc": 0.0005, "scale": 0.018},
        "skew": -0.1, "excess_kurtosis": 2.0, "jb_stat": 10.0, "jb_pvalue": 0.01,
    }
    rb.draw_distribution_chart("TEST", dist_data, returns, capture_fig)
    fig = capture_fig["fig"]
    ax = fig.axes[0]

    norm_line = next(ln for ln in ax.lines if ln.get_label().startswith("Normal Fit"))
    x_arr = norm_line.get_xdata()
    expected_y = scipy.stats.norm.pdf(x_arr, loc=dist_data["normal_fit"]["loc"], scale=dist_data["normal_fit"]["scale"])
    np.testing.assert_allclose(norm_line.get_ydata(), expected_y)

    t_line = next(ln for ln in ax.lines if ln.get_label().startswith("Student-t Fit"))
    expected_t = scipy.stats.t.pdf(
        x_arr, df=dist_data["t_fit"]["df"], loc=dist_data["t_fit"]["loc"], scale=dist_data["t_fit"]["scale"]
    )
    np.testing.assert_allclose(t_line.get_ydata(), expected_t)


# --------------------------------------------------------------------------- #
def test_52week_chart_plots_exact_window_and_bounds(capture_fig):
    df = _df(300)
    window = 252
    sub = df.iloc[-window:]
    stats_52w = {
        "window_used": window,
        "high": float(sub["Close"].max()),
        "low": float(sub["Close"].min()),
        "current": float(df["Close"].iloc[-1]),
        "position_pct": 42.0,
    }
    rb.draw_52week_chart("TEST", df, stats_52w, capture_fig)
    fig = capture_fig["fig"]
    ax = fig.axes[0]

    close_line = next(ln for ln in ax.lines if ln.get_label().startswith("TEST Close"))
    np.testing.assert_allclose(close_line.get_ydata(), sub["Close"].to_numpy())
    assert len(close_line.get_ydata()) == window  # only the window, not full history

    high_line = next(ln for ln in ax.lines if ln.get_label().startswith("52w High"))
    assert high_line.get_ydata()[0] == pytest.approx(stats_52w["high"])
    low_line = next(ln for ln in ax.lines if ln.get_label().startswith("52w Low"))
    assert low_line.get_ydata()[0] == pytest.approx(stats_52w["low"])


# --------------------------------------------------------------------------- #
def test_drawdown_chart_plots_exact_values(capture_fig):
    idx = pd.date_range("2024-01-01", periods=100, freq="B")
    dd_series = pd.DataFrame({"drawdown": -np.abs(_series(idx, 22).cumsum()) / 100})
    rb.draw_drawdown_chart("TEST", dd_series, capture_fig)
    fig = capture_fig["fig"]
    ax = fig.axes[0]
    line = next(ln for ln in ax.lines if ln.get_label() == "Drawdown %")
    np.testing.assert_allclose(line.get_ydata(), dd_series["drawdown"].to_numpy() * 100.0)


# --------------------------------------------------------------------------- #
def test_beta_chart_scatter_and_regression_match_inputs(capture_fig):
    idx = pd.date_range("2024-01-01", periods=100, freq="B")
    stock_ret = _series(idx, 23) * 0.01
    bench_ret = _series(idx, 24) * 0.01
    beta, alpha_daily = 1.3, 0.0002
    rb.draw_beta_chart("TEST", stock_ret, bench_ret, beta, alpha_daily, capture_fig)
    fig = capture_fig["fig"]
    ax = fig.axes[0]

    scatter = ax.collections[0]
    offsets = scatter.get_offsets()
    np.testing.assert_allclose(np.sort(offsets[:, 0]), np.sort(bench_ret.to_numpy()))
    np.testing.assert_allclose(np.sort(offsets[:, 1]), np.sort(stock_ret.to_numpy()))

    reg_line = next(ln for ln in ax.lines if ln.get_label().startswith("Regression"))
    x_arr = reg_line.get_xdata()
    expected_y = beta * x_arr + alpha_daily
    np.testing.assert_allclose(reg_line.get_ydata(), expected_y)


# --------------------------------------------------------------------------- #
def test_structural_breaks_chart_axvlines_match_break_dates(capture_fig):
    df = _df(50)
    # Break indices are positions in the RETURNS series (one shorter than
    # prices: diff().dropna() drops the first row), so a break at returns
    # position k carries the date df.index[k+1]. The chart line must land
    # exactly on the break's own stored date — the same one the JSON sidecar
    # and the markdown report show — not one bar early.
    breaks = [
        {"date": str(df.index[21].date()), "index": 20, "type": "mean_shift"},
        {"date": str(df.index[36].date()), "index": 35, "type": "volatility_shift"},
    ]
    rb.draw_structural_breaks_chart("TEST", df, breaks, capture_fig)
    fig = capture_fig["fig"]
    ax = fig.axes[0]

    break_lines = [ln for ln in ax.lines if ln.get_label().startswith("Break:")]
    plotted_dates = sorted(pd.Timestamp(ln.get_xdata()[0]) for ln in break_lines)
    expected_dates = sorted(pd.Timestamp(b["date"]) for b in breaks)
    assert plotted_dates == expected_dates


def test_structural_breaks_chart_unparseable_date_falls_back_positionally(capture_fig):
    """With an unparseable date the chart must still land on df.index[k+1]
    (the correct returns→prices shift), not df.index[k]."""
    df = _df(50)
    breaks = [{"date": "not-a-date", "index": 20, "type": "mean_shift"}]
    rb.draw_structural_breaks_chart("TEST", df, breaks, capture_fig)
    fig = capture_fig["fig"]
    ax = fig.axes[0]

    break_lines = [ln for ln in ax.lines if ln.get_label().startswith("Break:")]
    assert pd.Timestamp(break_lines[0].get_xdata()[0]) == df.index[21]


# --------------------------------------------------------------------------- #
def test_hurst_chart_scatter_matches_rs_values(capture_fig):
    ret_h = {"scales": [10, 20, 40, 80], "rs_values": [1.5, 2.1, 3.0, 4.2], "hurst": 0.55}
    vol_h = {"scales": [10, 20, 40, 80], "rs_values": [1.1, 1.6, 2.2, 3.1], "hurst": 0.48}
    rb.draw_hurst_chart("TEST", ret_h, vol_h, capture_fig)
    fig = capture_fig["fig"]
    ax = fig.axes[0]

    ret_scatter = ax.collections[0]
    offsets = ret_scatter.get_offsets()
    np.testing.assert_allclose(np.sort(offsets[:, 0]), np.sort(np.log(ret_h["scales"])))
    np.testing.assert_allclose(np.sort(offsets[:, 1]), np.sort(np.log(ret_h["rs_values"])))


# --------------------------------------------------------------------------- #
def test_quantile_beta_chart_plots_exact_values(capture_fig):
    quantiles = [0.1, 0.25, 0.5, 0.75, 0.9]
    qbeta_res = {
        "quantiles": quantiles,
        "betas": {q: 1.0 + 0.1 * i for i, q in enumerate(quantiles)},
        "cis": {q: (1.0 + 0.1 * i - 0.2, 1.0 + 0.1 * i + 0.2) for i, q in enumerate(quantiles)},
        "ols_beta": 1.15,
    }
    rb.draw_quantile_beta_chart("TEST", qbeta_res, capture_fig)
    fig = capture_fig["fig"]
    ax = fig.axes[0]

    beta_line = next(ln for ln in ax.lines if ln.get_label() == "Quantile Beta")
    np.testing.assert_allclose(beta_line.get_ydata(), [qbeta_res["betas"][q] for q in quantiles])

    ols_line = next(ln for ln in ax.lines if ln.get_label().startswith("OLS Beta"))
    assert ols_line.get_ydata()[0] == pytest.approx(qbeta_res["ols_beta"])


# --------------------------------------------------------------------------- #
def test_weekly_chart_data_fidelity(capture_fig):
    dates = pd.date_range("2026-01-01", periods=10, freq="W-FRI")
    weekly_df = pd.DataFrame({
        "Close": [10.0, 11.0, 12.0, 11.0, 10.0, 9.0, 10.0, 11.0, 12.0, 13.0],
    }, index=dates)
    sma10 = pd.Series([9.5] * 10, index=dates)
    sma40 = pd.Series([9.0] * 10, index=dates)
    weekly_rsi = pd.Series([50.0] * 10, index=dates)
    
    rb.draw_weekly_chart("TEST", weekly_df, sma10, sma40, weekly_rsi, capture_fig)
    fig = capture_fig["fig"]
    ax1, ax2 = fig.axes
    
    # Check Price axis (ax1)
    close_line = next(ln for ln in ax1.lines if ln.get_label() == "Weekly Close")
    np.testing.assert_allclose(close_line.get_ydata(), weekly_df["Close"].values)
    
    sma10_line = next(ln for ln in ax1.lines if ln.get_label() == "SMA (10)")
    np.testing.assert_allclose(sma10_line.get_ydata(), sma10.values)

    sma40_line = next(ln for ln in ax1.lines if ln.get_label() == "SMA (40)")
    np.testing.assert_allclose(sma40_line.get_ydata(), sma40.values)
    
    # Check RSI axis (ax2)
    rsi_line = next(ln for ln in ax2.lines if ln.get_label() == "Weekly RSI (14)")
    np.testing.assert_allclose(rsi_line.get_ydata(), weekly_rsi.values)


def test_volume_profile_chart_data_fidelity(capture_fig):
    df = _df()
    vp_data = {
        "poc": 100.0,
        "vah": 105.0,
        "val": 95.0,
        "volumes": [10.0, 20.0, 30.0],
        "bins": [90.0, 96.67, 103.33, 110.0],
        "status": "ok",
    }
    rb.draw_volume_profile_chart("TEST", df, vp_data, capture_fig)
    fig = capture_fig["fig"]
    ax1 = fig.axes[0]
    
    bars = ax1.containers[0]
    widths = [b.get_width() for b in bars]
    np.testing.assert_allclose(widths, vp_data["volumes"])


def test_volume_profile_weekly_chart_data_fidelity(capture_fig):
    df = _df()
    vpw_data = {
        "poc_weekly": 100.0,
        "vah_weekly": 105.0,
        "val_weekly": 95.0,
        "volumes": [10.0, 20.0, 30.0],
        "bins": [90.0, 96.67, 103.33, 110.0],
        "status": "ok",
    }
    rb.draw_volume_profile_weekly_chart("TEST", df, vpw_data, capture_fig)
    fig = capture_fig["fig"]
    ax1 = fig.axes[0]
    
    bars = ax1.containers[0]
    widths = [b.get_width() for b in bars]
    np.testing.assert_allclose(widths, vpw_data["volumes"])


def test_fibonacci_chart_data_fidelity(capture_fig):
    df = _df()
    fib_data = {
        "status": "ok",
        "swing_high": 110.0,
        "swing_low": 90.0,
        "direction": "up",
        "levels": {
            0.236: 105.28,
            0.382: 102.36,
            0.5: 100.0,
            0.618: 97.64,
            0.786: 94.28,
        },
    }
    rb.draw_fibonacci_chart("TEST", df, fib_data, capture_fig)
    fig = capture_fig["fig"]
    ax = fig.axes[0]
    
    lines = [ln.get_ydata()[0] for ln in ax.lines if len(ln.get_ydata()) > 0 and ln.get_label() != "Close"]
    expected_values = [105.28, 102.36, 100.0, 97.64, 94.28, 110.0, 90.0]
    for val in expected_values:
        assert any(abs(line_val - val) < 1e-4 for line_val in lines)


def test_donchian_chart_data_fidelity(capture_fig):
    df = _df()
    don_data = {
        "status": "ok",
        "upper_20": pd.Series([110.0] * len(df), index=df.index),
        "lower_20": pd.Series([90.0] * len(df), index=df.index),
        "mid_20": pd.Series([100.0] * len(df), index=df.index),
        "upper_55": pd.Series([115.0] * len(df), index=df.index),
        "lower_55": pd.Series([85.0] * len(df), index=df.index),
        "mid_55": pd.Series([100.0] * len(df), index=df.index),
    }
    rb.draw_donchian_chart("TEST", df, don_data, capture_fig)
    fig = capture_fig["fig"]
    ax = fig.axes[0]
    
    upper_line = next(ln for ln in ax.lines if ln.get_label() == "55-day Upper")
    np.testing.assert_allclose(upper_line.get_ydata(), don_data["upper_55"].values)
    
    lower_line = next(ln for ln in ax.lines if ln.get_label() == "55-day Lower")
    np.testing.assert_allclose(lower_line.get_ydata(), don_data["lower_55"].values)


def test_volume_chart_with_mfi_avwap_fidelity(capture_fig):
    df = _df()
    vwap = pd.Series([100.0] * len(df), index=df.index)
    obv = pd.Series([5000.0] * len(df), index=df.index)
    mfi = pd.Series([50.0] * len(df), index=df.index)
    avwap_ytd = pd.Series([99.0] * len(df), index=df.index)
    avwap_high = pd.Series([102.0] * len(df), index=df.index)
    avwap_low = pd.Series([98.0] * len(df), index=df.index)
    
    rb.draw_volume_chart(
        "TEST", df, vwap, obv, mfi, avwap_ytd, avwap_high, avwap_low, capture_fig
    )
    
    fig = capture_fig["fig"]
    ax1 = fig.axes[0]
    ax2 = fig.axes[1]
    
    close_line = next(ln for ln in ax1.lines if ln.get_label() == "TEST Close")
    np.testing.assert_allclose(close_line.get_ydata(), df["Close"].values)
    
    ytd_line = next(ln for ln in ax1.lines if ln.get_label() == "AVWAP YTD")
    np.testing.assert_allclose(ytd_line.get_ydata(), avwap_ytd.values)
    
    mfi_line = next(ln for ln in ax2.lines if ln.get_label() == "MFI (14)")
    np.testing.assert_allclose(mfi_line.get_ydata(), mfi.values)


def test_candles_chart_data_fidelity(capture_fig):
    df = _df(60)
    doji_series = pd.Series([False] * len(df), index=df.index)
    doji_series.iloc[-1] = True
    
    trend_data = {
        "sma20": pd.Series([100.0] * len(df), index=df.index),
        "sma50": pd.Series([100.0] * len(df), index=df.index),
        "candle_patterns": {
            "doji": doji_series,
            "hammer": pd.Series([False] * len(df), index=df.index),
            "shooting_star": pd.Series([False] * len(df), index=df.index),
            "bullish_engulfing": pd.Series([False] * len(df), index=df.index),
            "bearish_engulfing": pd.Series([False] * len(df), index=df.index),
        }
    }
    rb.draw_candles_chart("TEST", df, trend_data, capture_fig, n=60)
    fig = capture_fig["fig"]
    ax = fig.axes[0]
    
    scatter = next(coll for coll in ax.collections if coll.get_label() == "Doji")
    offsets = scatter.get_offsets()
    assert offsets[0][0] == 59

