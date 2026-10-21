"""风险与绩效指标库的单元测试。

运行：python -m pytest trader/tests -q
不需要 vnpy / 行情数据——全部用构造的净值/收益序列验证数学口径。
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "cta_backtesting"))

from risk_metrics import (  # noqa: E402
    RiskLimits,
    compute_risk_metrics,
    cumulative_to_returns,
    evaluate_risk_gate,
    max_drawdown,
    monthly_returns,
    nav_to_returns,
    position_exposure_summary,
    ulcer_index,
    value_at_risk,
)


# ---------------- 序列转换 ----------------

def test_nav_to_returns_basic():
    nav = [100.0, 110.0, 99.0]
    rets = nav_to_returns(nav)
    assert rets.size == 2
    assert abs(rets[0] - 0.10) < 1e-9
    assert abs(rets[1] - (99.0 / 110.0 - 1.0)) < 1e-9


def test_nav_to_returns_handles_non_positive():
    """净值跌破 0 时收益记 0，不产生 inf/nan。

    注意守卫条件：看的是**前一日**净值是否为正。100→0 是真实的 -100%，
    保留；0→-50 因前一日净值非正而被置 0。
    """
    rets = nav_to_returns([100.0, 0.0, -50.0, 120.0])
    assert np.all(np.isfinite(rets))
    assert rets[0] == -1.0            # 100 -> 0，真实的 -100%
    assert rets[1] == 0.0             # 0 -> -50，前一值非正，置 0
    assert rets[2] == 0.0             # -50 -> 120，前一值非正，置 0


def test_cumulative_to_returns_roundtrip():
    """区间累计收益% → 日收益 → 重新累计应还原。"""
    cum = [0.0, 10.0, -5.0, 20.0]
    rets = cumulative_to_returns(cum)
    assert rets.size == 3
    rebuilt = np.cumprod(1.0 + rets) - 1.0
    assert abs(rebuilt[-1] * 100 - 20.0) < 1e-9


# ---------------- 最大回撤 ----------------

def test_max_drawdown_known_case():
    nav = [100.0, 120.0, 90.0, 130.0]
    info = max_drawdown(nav)
    # 峰值 120 → 谷值 90 = -25%
    assert abs(info["max_dd_pct"] - (-25.0)) < 1e-6
    assert info["peak_index"] == 1
    assert info["trough_index"] == 2
    assert info["duration_days"] == 1


def test_max_drawdown_monotonic_up_is_zero():
    info = max_drawdown([100.0, 101.0, 105.0, 110.0])
    assert info["max_dd_pct"] == 0.0


def test_max_drawdown_insufficient_data():
    assert max_drawdown([100.0])["max_dd_pct"] == 0.0
    assert max_drawdown([])["max_dd_pct"] == 0.0


def test_ulcer_index_zero_for_monotonic():
    assert ulcer_index([100.0, 110.0, 120.0]) == 0.0


def test_ulcer_index_positive_with_drawdown():
    assert ulcer_index([100.0, 120.0, 90.0, 130.0]) > 0.0


# ---------------- VaR ----------------

def test_var_symmetric_distribution():
    rng = np.random.default_rng(42)
    rets = rng.normal(0, 0.01, 5000)
    out = value_at_risk(rets, 0.95)
    # 正态 N(0, 1%) 的 5% 分位 ≈ -1.645% → VaR ≈ 1.645%
    assert 1.2 < out["var_pct"] < 2.2
    # CVaR 应大于 VaR（尾部平均损失更深）
    assert out["cvar_pct"] >= out["var_pct"]


def test_var_empty_input():
    out = value_at_risk([], 0.95)
    assert out["var_pct"] == 0.0 and out["cvar_pct"] == 0.0


# ---------------- 完整指标集 ----------------

def test_compute_risk_metrics_empty():
    m = compute_risk_metrics([])
    assert m["samples"] == 0
    assert m["sharpe_ratio"] == 0.0


def test_compute_risk_metrics_flat_series():
    """零收益序列：波动为 0，夏普/索提诺应为 0 而不是除零崩溃。"""
    m = compute_risk_metrics([0.0] * 60)
    assert m["samples"] == 60
    assert m["annual_volatility_pct"] == 0.0
    assert m["sharpe_ratio"] == 0.0
    assert m["sortino_ratio"] == 0.0
    assert m["max_drawdown_pct"] == 0.0
    assert m["degenerate"] is True


def test_compute_risk_metrics_float_noise_does_not_explode():
    """回归：权益曲线只有浮点噪声时，夏普必须是 0 而不是 ±1e7。

    真实场景：策略在样本期内没有成交，balance 恒等于 capital，
    `curr/prev - 1` 会产出 ~1e-10 的日收益，直接算比率会得到
    sharpe = -12915183 这种无意义数值。
    """
    np.random.seed(1)
    bal = 10000.0 + np.cumsum(np.random.normal(0, 1e-6, 400))
    m = compute_risk_metrics(nav_to_returns(list(bal)))
    assert m["sharpe_ratio"] == 0.0
    assert m["sortino_ratio"] == 0.0
    assert m["calmar_ratio"] == 0.0
    assert m["annual_volatility_pct"] == 0.0
    assert m["degenerate"] is True
    assert "degenerate_reason" in m


def test_compute_risk_metrics_no_trade_series_is_degenerate():
    """完全无成交：日收益全 0，必须标记 degenerate 且比率全 0。"""
    m = compute_risk_metrics([0.0] * 300)
    assert m["samples"] == 300
    assert m["total_return_pct"] == 0.0
    assert m["sharpe_ratio"] == 0.0
    assert m["degenerate"] is True


def test_compute_risk_metrics_positive_drift():
    """强正漂移：夏普、索提诺、Calmar 都应为正，年化收益接近漂移的几何均值。"""
    rng = np.random.default_rng(11)
    rets = rng.normal(0.001, 0.008, 500)  # 日 ~0.10%，波动 0.8%
    m = compute_risk_metrics(rets, risk_free=0.02)
    assert m["samples"] == 500
    assert m["total_return_pct"] > 0
    assert m["sharpe_ratio"] > 0
    assert m["sortino_ratio"] > 0
    assert m["calmar_ratio"] > 0
    assert 0.0 < m["daily_win_rate"] < 1.0
    assert m["var_95_pct"] > 0
    assert m["periods_per_year"] == 252


def test_compute_risk_metrics_negative_drift_flags_loss():
    """负漂移序列：总收益为负，但指标仍须全部可算（不出现 None/NaN）。"""
    rng = np.random.default_rng(7)
    rets = rng.normal(-0.001, 0.01, 300)
    m = compute_risk_metrics(rets)
    assert m["total_return_pct"] < 0
    assert m["max_drawdown_pct"] < 0
    assert m["sharpe_ratio"] < 0
    assert all(v is not None for v in m.values())


def test_sortino_and_sharpe_both_negative_when_all_downside():
    """全下行序列：夏普为负；索提诺在下行亏损完全一致时退化为 0（分母为 0 的合理兜底）。"""
    rets = np.array([0.0] * 20 + [-0.02] * 10)  # 亏损全部相等 → 下行波动为 0
    m = compute_risk_metrics(rets)
    assert m["sharpe_ratio"] < 0
    assert m["sortino_ratio"] == 0.0   # 下行离散度为 0 时返回 0，不做除零
    assert m["daily_win_rate"] == 0.0


def test_sortino_negative_with_varied_downside():
    """亏损幅度不一时，索提诺应为负且与夏普同号。"""
    rng = np.random.default_rng(5)
    rets = rng.normal(-0.001, 0.012, 300)
    m = compute_risk_metrics(rets)
    assert m["sharpe_ratio"] < 0
    assert m["sortino_ratio"] < 0


def test_monthly_returns_aggregation():
    dates = ["2025-01-01", "2025-01-15", "2025-02-01", "2025-02-20"]
    rets = [0.01, 0.01, 0.02, -0.01]
    out = monthly_returns(dates, rets)
    assert len(out) == 2
    assert out[0]["month"] == "2025-01"
    assert abs(out[0]["return_pct"] - 2.01) < 1e-6  # 1.01*1.01-1
    assert out[1]["return_pct"] < out[0]["return_pct"]


def test_monthly_returns_length_mismatch_returns_empty():
    assert monthly_returns(["2025-01-01"], [0.01, 0.02]) == []


def test_monthly_returns_with_nav_derived_returns():
    """回归：n 个净值产生 n-1 个日收益，日期必须同步去掉首日才能对齐。

    之前 chooseStrategy 传的是完整 dates（n 个）+ rets（n-1 个），
    monthly_returns 长度校验失败静默返回 []，前端月度收益表永远是空的。
    """
    nav = [100.0, 101.0, 102.0, 103.0]
    dates = ["2025-01-01", "2025-01-02", "2025-02-03", "2025-02-04"]
    rets = nav_to_returns(nav)
    assert rets.size == len(nav) - 1
    out = monthly_returns(dates[1:], rets)   # 正确用法：日期也去掉首日
    assert len(out) == 2
    assert out[0]["month"] == "2025-01"
    assert out[1]["month"] == "2025-02"


# ---------------- 风控闸门 ----------------

def _good_metrics():
    rng = np.random.default_rng(11)
    return compute_risk_metrics(rng.normal(0.0006, 0.006, 400))


def _bad_metrics():
    rng = np.random.default_rng(3)
    return compute_risk_metrics(rng.normal(-0.002, 0.03, 400))


def test_gate_approves_healthy_strategy():
    res = evaluate_risk_gate(_good_metrics())
    assert res["approved"] is True
    assert res["verdict"] == "APPROVE"
    assert res["reasons"] == []
    assert len(res["checks"]) >= 4


def test_gate_rejects_high_drawdown():
    m = _good_metrics()
    m["max_drawdown_pct"] = -40.0
    res = evaluate_risk_gate(m)
    assert res["approved"] is False
    assert res["verdict"] == "REJECT"
    assert any("回撤" in r for r in res["reasons"])
    failed = [c for c in res["checks"] if not c["passed"]]
    assert any(c["rule"] == "max_drawdown" for c in failed)


def test_gate_rejects_insufficient_samples():
    m = _good_metrics()
    m["samples"] = 5
    res = evaluate_risk_gate(m)
    assert res["approved"] is False
    assert any(c["rule"] == "min_samples" for c in res["checks"] if not c["passed"])


def test_gate_rejects_var_breach():
    m = _bad_metrics()
    res = evaluate_risk_gate(m)
    assert res["approved"] is False
    assert any(c["rule"] == "var_95" for c in res["checks"] if not c["passed"])


def test_gate_custom_limits():
    m = _good_metrics()
    lim = RiskLimits(max_drawdown_pct=1.0, min_samples=10_000)
    res = evaluate_risk_gate(m, limits=lim)
    assert res["approved"] is False
    assert len(res["reasons"]) >= 2


def test_gate_rejects_degenerate_series():
    """无有效波动的序列不得通过风控闸门（否则无交易策略会被判为"安全"）。"""
    m = compute_risk_metrics([0.0] * 300)
    res = evaluate_risk_gate(m)
    assert res["approved"] is False
    assert res["verdict"] == "REJECT"
    assert any(c["rule"] == "non_degenerate" for c in res["checks"] if not c["passed"])
    assert any("无有效波动" in r for r in res["reasons"])


def test_gate_position_check_optional():
    m = _good_metrics()
    assert evaluate_risk_gate(m)["approved"] is True
    res = evaluate_risk_gate(m, max_position_pct=150.0)
    assert res["approved"] is False
    assert any(c["rule"] == "max_position" for c in res["checks"] if not c["passed"])


# ---------------- 仓位暴露 ----------------

class _FakeRow:
    def __init__(self, d):
        self._d = d

    def __getitem__(self, k):
        return self._d.get(k, 0)

    def get(self, k, default=None):
        return self._d.get(k, default)


class _FakeDF:
    def __init__(self, rows):
        self._rows = rows
        self.empty = not rows

    def iterrows(self):
        for r in self._rows:
            yield None, _FakeRow(r)


def test_position_exposure_summary():
    df = _FakeDF([
        {"end_pos": 0, "close_price": 10.0, "balance": 100_000.0},
        {"end_pos": 100, "close_price": 10.0, "balance": 100_000.0},  # 1% 敞口
        {"end_pos": 1000, "close_price": 10.0, "balance": 100_000.0},  # 10% 敞口
    ])
    out = position_exposure_summary(df, size=1.0)
    assert out["days"] == 3
    assert abs(out["max_position_pct"] - 10.0) < 1e-6
    assert out["exposure_days_ratio"] == pytest.approx(2 / 3, rel=1e-3)


def test_position_exposure_summary_empty():
    out = position_exposure_summary(_FakeDF([]))
    assert out["days"] == 0
    assert out["max_position_pct"] == 0.0
