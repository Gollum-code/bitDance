"""量化扩展模块单测：Monte Carlo / Walk-forward / 因子 IC。

全部为纯函数或注入假回测桩，不需要 vnpy 与网络。
运行：python -m pytest trader/tests -q
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "cta_backtesting"))

from factor_ic import (  # noqa: E402
    forward_returns,
    ic_statistics,
    information_coefficient,
    quantile_returns,
    summarize_factor,
)
from monte_carlo import (  # noqa: E402
    block_bootstrap_returns,
    monte_carlo_summary,
    parameter_stability,
)
from rewritten_strategies._family_helpers import StopManager, make_stop_aware  # noqa: E402
from walk_forward import run_walk_forward, split_walk_forward  # noqa: E402


# ---------------- Monte Carlo ----------------

def _series(n=300, mu=0.0005, sigma=0.012, seed=7):
    rng = np.random.default_rng(seed)
    return rng.normal(mu, sigma, n)


def test_block_bootstrap_shape_and_determinism():
    rets = _series()
    a = block_bootstrap_returns(rets, sims=50, block=10, seed=123)
    b = block_bootstrap_returns(rets, sims=50, block=10, seed=123)
    assert a.shape == (50, rets.size)
    assert np.allclose(a, b)  # 同 seed 同结果


def test_block_bootstrap_non_divisible_sample():
    """样本长度不是块长整数倍时不能报 broadcast 错误。"""
    rets = _series(120)
    out = block_bootstrap_returns(rets, sims=8, block=20, seed=1)
    assert out.shape == (8, 120)
    assert np.all(np.isfinite(out))


def test_monte_carlo_summary_structure():
    out = monte_carlo_summary(_series(), sims=200, block=10, seed=1)
    assert out["ok"] is True
    for key in ("total_return", "annual_return", "sharpe", "max_drawdown"):
        block = out[key]
        assert block["p05"] <= block["p50"] <= block["p95"]
        assert 0.0 <= block["prob_positive"] <= 1.0
    assert len(out["sharpe_ci"]) == 2
    assert out["sharpe_ci"][0] <= out["sharpe_ci"][1]
    assert out["drawdown_p95"] >= 0
    assert set(out["band"]) == {"lo", "mid", "hi"}
    assert len(out["band"]["mid"]) == 300
    # 逐日带应满足 lo <= mid <= hi
    assert out["band"]["lo"][-1] <= out["band"]["mid"][-1] <= out["band"]["hi"][-1]
    assert out["interpretation"]


def test_monte_carlo_insufficient_samples():
    out = monte_carlo_summary([0.01, -0.01], sims=100)
    assert out["ok"] is False
    assert "样本" in out["reason"]


def test_parameter_stability_detects_isolated_peak():
    out = parameter_stability([5, 10, 15, 20], [0.2, 0.3, 2.5, 0.25])
    assert out["ok"] is True
    assert out["isolated_peak"] is True
    assert out["best_param"] == 15
    assert "过拟合" in out["verdict"]


def test_parameter_stability_smooth_curve():
    out = parameter_stability([5, 10, 15, 20], [0.8, 1.0, 1.1, 1.05])
    assert out["isolated_peak"] is False


def test_parameter_stability_needs_three_points():
    out = parameter_stability([5, 10], [1.0, 2.0])
    assert out["ok"] is False


# ---------------- Walk-forward ----------------

def test_split_walk_forward_count_and_order():
    folds = split_walk_forward("2022-01-01", "2024-01-01", n_splits=4, embargo_days=5)
    assert len(folds) >= 3
    for f in folds:
        assert f["train_start"] <= f["train_end"] < f["test_start"] <= f["test_end"]
    assert folds[0]["train_start"] == "2022-01-01"


def test_split_walk_forward_rejects_short_range():
    with pytest.raises(ValueError):
        split_walk_forward("2024-01-01", "2024-02-01", n_splits=4)


def test_run_walk_forward_consistency_and_degradation():
    folds = split_walk_forward("2020-01-01", "2024-01-01", n_splits=4, embargo_days=0)
    test_starts = {f["test_start"] for f in folds}

    def run_fn(params, start, end):
        # 人为制造：样本外只有样本内的 40% 表现
        mult = 0.4 if start in test_starts else 1.0
        return {
            "ok": True,
            "sharpe": params["x"] * mult,
            "total_return": params["x"] * mult,
            "calmar": params["x"] * mult,
            "max_drawdown": 5.0,
            "trade_count": 10,
        }

    out = run_walk_forward(
        [{"x": 1.0}, {"x": 2.0}, {"x": 3.0}],
        start="2020-01-01",
        end="2024-01-01",
        run_fn=run_fn,
        n_splits=4,
        embargo_days=0,
        apply_risk_gate=False,
    )
    assert out["ok"] is True
    assert len(out["folds"]) == len(folds)
    assert out["efficiency_ratio"] == pytest.approx(0.4, abs=0.05)
    assert out["overfit_probability"] > 0.5
    assert "退化" in out["verdict"] or "过拟合" in out["verdict"]


def test_run_walk_forward_all_fail():
    out = run_walk_forward(
        [{"x": 1.0}],
        start="2020-01-01",
        end="2024-01-01",
        run_fn=lambda p, s, e: {"ok": False, "error": "no data"},
        n_splits=3,
        embargo_days=0,
    )
    assert out["ok"] is False
    assert "失败" in out["reason"]


# ---------------- 因子 IC ----------------

def test_forward_returns_tail_nan():
    close = np.array([1.0, 1.1, 1.2, 1.3, 1.4])
    fwd = forward_returns(close, 2)
    assert np.isnan(fwd[-2:]).all()
    assert fwd[0] == pytest.approx(1.2 / 1.0 - 1.0)


def test_information_coefficient_perfect_rank():
    f = [1, 2, 3, 4, 5]
    r = [10, 20, 30, 40, 50]
    assert information_coefficient(f, r) == pytest.approx(1.0)
    assert information_coefficient(f, r[::-1]) == pytest.approx(-1.0)


def test_information_coefficient_handles_nan_and_ties():
    f = [1, 2, 2, 4, np.nan]
    r = [0.1, 0.2, 0.2, 0.4, 0.9]
    ic = information_coefficient(f, r)
    assert ic is not None
    assert -1.0 <= ic <= 1.0


def test_ic_statistics():
    out = ic_statistics([0.1, 0.2, -0.05, 0.15, 0.05])
    assert out["periods"] == 5
    assert out["positive_ratio"] == pytest.approx(0.8)
    assert out["ic_mean"] > 0
    assert out["ic_ir"] > 0
    assert out["t_stat"] > 0


def test_quantile_returns_monotonic():
    f = np.arange(100, dtype=float)
    r = np.arange(100, dtype=float) * 0.001
    out = quantile_returns(f, r, quantiles=5)
    assert out["ok"] is True
    assert out["direction"] == "positive"
    assert out["monotonicity"] == pytest.approx(1.0)


def test_summarize_factor_verdicts():
    effective = summarize_factor([0.05] * 20)
    assert effective["verdict"] in ("effective", "weak")
    ineffective = summarize_factor([0.001, -0.001] * 10)
    assert ineffective["verdict"] == "ineffective"
    insufficient = summarize_factor([])
    assert insufficient["verdict"] == "insufficient"


# ---------------- StopManager ----------------

def test_stop_manager_disabled_by_default():
    sm = StopManager(0, 0, 0)
    assert sm.enabled is False
    sm.on_open(True, 100.0)
    assert sm.check(50.0, 1) is None  # 不配置止损时永不触发


def test_stop_manager_stop_loss_long():
    sm = StopManager(stop_loss_pct=5.0)
    sm.on_open(True, 100.0)
    assert sm.check(96.0, 1) is None
    assert sm.check(94.9, 1) == "stop_loss"


def test_stop_manager_take_profit_long():
    sm = StopManager(take_profit_pct=10.0)
    sm.on_open(True, 100.0)
    assert sm.check(109.0, 1) is None
    assert sm.check(110.0, 1) == "take_profit"


def test_stop_manager_trailing_stop_long():
    sm = StopManager(trailing_stop_pct=5.0)
    sm.on_open(True, 100.0)
    sm.check(120.0, 1)            # 峰值抬到 120
    assert sm.check(116.0, 1) is None
    assert sm.check(113.0, 1) == "trailing_stop"


def test_stop_manager_short_side():
    sm = StopManager(stop_loss_pct=5.0, take_profit_pct=10.0)
    sm.on_open(False, 100.0)
    assert sm.check(95.0, -1) is None      # 空头下跌是盈利
    assert sm.check(90.0, -1) == "take_profit"
    sm.on_open(False, 100.0)
    assert sm.check(106.0, -1) == "stop_loss"


def test_stop_manager_resets_on_close():
    sm = StopManager(stop_loss_pct=5.0)
    sm.on_open(True, 100.0)
    sm.on_close()
    assert sm.direction == 0
    assert sm.check(1.0, 0) is None


def test_make_stop_aware_adds_parameters():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "cta_backtesting"))
    from run_rewritten_strategy_backtest import load_strategy_class

    cls, _ = load_strategy_class("01")
    wrapped = make_stop_aware(cls)
    assert wrapped is not cls
    for p in ("stop_loss_pct", "take_profit_pct", "trailing_stop_pct"):
        assert p in wrapped.parameters
    # 原子策略参数仍在
    for p in cls.parameters:
        assert p in wrapped.parameters
    assert issubclass(wrapped, cls)
