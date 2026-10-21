"""风险与绩效指标库（纯函数）。

vn.py 的 `calculate_statistics()` 只给出夏普、最大回撤等基础指标，
缺少下行风险、尾部风险与仓位暴露视角。本模块补齐这些口径，
并提供一个**确定性硬规则风控闸门**（不依赖任何 LLM 判断）。

设计原则：
  1. 所有函数输入 numpy 数组 / 标量，不读写全局状态，便于单测。
  2. 所有指标显式标注口径（日频、年化 252、无风险利率参数化），
     避免报告里出现"夏普 1.8"却说不清怎么算的情况。
  3. 风控闸门只做布尔判定 + 拒绝原因列表，判定逻辑可审计。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

TRADING_DAYS = 252


def nav_to_returns(nav: Iterable[float]) -> np.ndarray:
    """净值序列 → 日收益率序列。首日收益记为 0，非正净值位置置 0。"""
    arr = np.asarray(list(nav), dtype=float)
    if arr.size < 2:
        return np.zeros(0, dtype=float)
    prev = arr[:-1]
    curr = arr[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        rets = np.where(prev > 1e-12, curr / prev - 1.0, 0.0)
    rets = np.nan_to_num(rets, nan=0.0, posinf=0.0, neginf=0.0)
    return rets


def cumulative_to_returns(cum_pct: Iterable[float]) -> np.ndarray:
    """区间累计收益（%）→ 日收益率。用于多策略对比返回的 returns 序列。"""
    arr = np.asarray(list(cum_pct), dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size < 2:
        return np.zeros(0, dtype=float)
    nav = 1.0 + arr / 100.0
    return nav_to_returns(nav)


def max_drawdown(nav: Iterable[float]) -> dict[str, Any]:
    """最大回撤（净值口径）。

    返回最大回撤百分比、峰值/谷值位置、回撤持续交易日数。
    """
    arr = np.asarray(list(nav), dtype=float)
    if arr.size < 2:
        return {"max_dd_pct": 0.0, "peak_index": 0, "trough_index": 0, "duration_days": 0}

    peak = np.maximum.accumulate(arr)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = np.where(peak > 1e-12, arr / peak - 1.0, 0.0)
    dd = np.nan_to_num(dd, nan=0.0, posinf=0.0, neginf=0.0)
    trough = int(np.argmin(dd))
    peak_idx = int(np.argmax(arr[: trough + 1])) if trough >= 0 else 0
    return {
        "max_dd_pct": round(float(dd[trough] * 100.0), 4),
        "peak_index": peak_idx,
        "trough_index": trough,
        "duration_days": max(0, trough - peak_idx),
    }


def ulcer_index(nav: Iterable[float]) -> float:
    """溃疡指数：回撤平方均值的平方根，惩罚长期深回撤（比单一最大回撤更全面）。"""
    arr = np.asarray(list(nav), dtype=float)
    if arr.size < 2:
        return 0.0
    peak = np.maximum.accumulate(arr)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = np.where(peak > 1e-12, arr / peak - 1.0, 0.0)
    dd = np.nan_to_num(dd, nan=0.0, posinf=0.0, neginf=0.0)
    return round(float(math.sqrt(np.mean(dd ** 2)) * 100.0), 4)


def value_at_risk(returns: Iterable[float], level: float = 0.95) -> dict[str, float]:
    """历史模拟法 VaR / CVaR（日频）。

    VaR(95%) = 日收益分布的 5% 分位数取绝对值。
    CVaR(95%) = 分位数以下所有损失的均值（尾部平均损失），比 VaR 更保守。
    """
    arr = np.asarray(list(returns), dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return {"var_pct": 0.0, "cvar_pct": 0.0, "level": level}

    alpha = 1.0 - level
    q = float(np.percentile(arr, alpha * 100.0))
    tail = arr[arr <= q]
    cvar = float(np.mean(tail)) if tail.size else q
    return {
        "var_pct": round(abs(q) * 100.0, 4),
        "cvar_pct": round(abs(cvar) * 100.0, 4),
        "level": level,
    }


def compute_risk_metrics(
    returns: Iterable[float],
    *,
    risk_free: float = 0.02,
    periods: int = TRADING_DAYS,
    min_active_ratio: float = 0.05,
) -> dict[str, Any]:
    """由日收益率计算完整风险/绩效指标集。

    口径说明：
      - 年化收益：几何年化，`(1+累计)^(periods/n) - 1`
      - 波动率：日收益标准差 × √periods
      - 夏普：`(年化收益 - risk_free) / 年化波动`
      - 索提诺：分母只用**下行波动率**（低于目标收益的部分）
      - Calmar：年化收益 / |最大回撤|
      - 偏度/峰度：日收益分布形状，用于识别尾部风险

    min_active_ratio：非零收益天数占比下限。低于该比例说明样本期内
    几乎没有交易（例如 400 天只成交 1 笔），此时的比率是噪声而非绩效，
    标记为 degenerate 并把风险比率归零，避免输出 sharpe = -232 这类数字。
    """
    arr = np.asarray(list(returns), dtype=float)
    arr = arr[~np.isnan(arr)]
    n = arr.size
    if n == 0:
        return _empty_metrics()

    total_return = float(np.prod(1.0 + arr) - 1.0)
    annual_return = (1.0 + total_return) ** (periods / n) - 1.0 if total_return > -1.0 else -1.0
    daily_std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    annual_vol = daily_std * math.sqrt(periods)

    active = int(np.sum(np.abs(arr) > 1e-12))
    active_ratio = active / n

    # 数值下限：权益曲线完全平坦时，日收益只剩浮点噪声（~1e-10 量级）。
    # 真实策略的日波动在 1e-3 量级，噪声与之相差 7 个数量级。
    # 阈值取日尺度 1e-8（年化约 1.6e-7），远低于任何真实策略，但能挡住浮点噪声。
    daily_noise_floor = 1e-8
    degenerate = daily_std < daily_noise_floor or active_ratio < min_active_ratio
    degenerate_reason = None
    if daily_std < daily_noise_floor:
        degenerate_reason = "权益曲线在样本期内无有效波动（可能无交易或数据异常），风险比率置 0"
    elif active_ratio < min_active_ratio:
        degenerate_reason = (
            f"样本期仅 {active}/{n} 天有盈亏（占比 {active_ratio:.1%}，低于 {min_active_ratio:.0%}），"
            "交易样本过少，风险比率不具统计意义"
        )

    if degenerate:
        return {
            "samples": n,
            "active_days": active,
            "active_ratio": round(active_ratio, 4),
            "total_return_pct": round(total_return * 100.0, 4),
            "annual_return_pct": round(annual_return * 100.0, 4),
            "annual_volatility_pct": round(annual_vol * 100.0, 4),
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_duration_days": 0,
            "ulcer_index_pct": 0.0,
            "var_95_pct": 0.0,
            "cvar_95_pct": 0.0,
            "daily_win_rate": round(float(np.sum(arr > 0)) / n, 4),
            "profit_factor_daily": None,
            "skew": 0.0,
            "excess_kurtosis": 0.0,
            "risk_free_rate": risk_free,
            "periods_per_year": periods,
            "degenerate": True,
            "degenerate_reason": degenerate_reason,
        }

    sharpe = ((annual_return - risk_free) / annual_vol)

    downside = arr[arr < 0.0]
    downside_std = float(np.std(downside, ddof=1)) if downside.size > 1 else 0.0
    annual_downside = downside_std * math.sqrt(periods)
    sortino = ((annual_return - risk_free) / annual_downside) if annual_downside > 1e-12 else 0.0

    nav = np.cumprod(1.0 + arr)
    nav = np.insert(nav, 0, 1.0)
    dd_info = max_drawdown(nav)
    max_dd_pct = dd_info["max_dd_pct"]
    calmar = (annual_return * 100.0 / abs(max_dd_pct)) if abs(max_dd_pct) > 1e-9 else 0.0

    var_info = value_at_risk(arr, 0.95)

    positive_days = int(np.sum(arr > 0))
    negative_days = int(np.sum(arr < 0))
    win_rate = positive_days / n if n else 0.0

    gains = arr[arr > 0]
    losses = arr[arr < 0]
    profit_factor = (
        float(np.sum(gains) / abs(np.sum(losses))) if losses.size and abs(np.sum(losses)) > 1e-12 else None
    )

    skew = float(_skew(arr)) if n > 2 else 0.0
    kurt = float(_kurtosis(arr)) if n > 3 else 0.0

    return {
        "samples": n,
        "active_days": active,
        "active_ratio": round(active_ratio, 4),
        "total_return_pct": round(total_return * 100.0, 4),
        "annual_return_pct": round(annual_return * 100.0, 4),
        "annual_volatility_pct": round(annual_vol * 100.0, 4),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "calmar_ratio": round(calmar, 4),
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_duration_days": dd_info["duration_days"],
        "ulcer_index_pct": ulcer_index(nav),
        "var_95_pct": var_info["var_pct"],
        "cvar_95_pct": var_info["cvar_pct"],
        "daily_win_rate": round(win_rate, 4),
        "profit_factor_daily": round(profit_factor, 4) if profit_factor is not None else None,
        "skew": round(skew, 4),
        "excess_kurtosis": round(kurt, 4),
        "risk_free_rate": risk_free,
        "periods_per_year": periods,
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "samples": 0,
        "total_return_pct": 0.0,
        "annual_return_pct": 0.0,
        "annual_volatility_pct": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "calmar_ratio": 0.0,
        "max_drawdown_pct": 0.0,
        "max_drawdown_duration_days": 0,
        "ulcer_index_pct": 0.0,
        "var_95_pct": 0.0,
        "cvar_95_pct": 0.0,
        "daily_win_rate": 0.0,
        "profit_factor_daily": None,
        "skew": 0.0,
        "excess_kurtosis": 0.0,
        "risk_free_rate": 0.02,
        "periods_per_year": TRADING_DAYS,
        "degenerate": True,
        "degenerate_reason": "无有效收益样本",
    }


def _skew(arr: np.ndarray) -> float:
    m = float(np.mean(arr))
    s = float(np.std(arr, ddof=0))
    if s < 1e-12:
        return 0.0
    return float(np.mean(((arr - m) / s) ** 3))


def _kurtosis(arr: np.ndarray) -> float:
    m = float(np.mean(arr))
    s = float(np.std(arr, ddof=0))
    if s < 1e-12:
        return 0.0
    return float(np.mean(((arr - m) / s) ** 4) - 3.0)


def monthly_returns(dates: Iterable[str], returns: Iterable[float]) -> list[dict[str, Any]]:
    """按自然月聚合日收益，返回月度收益表（便于看收益稳定性）。"""
    ds = list(dates)
    rs = np.asarray(list(returns), dtype=float)
    if not ds or len(ds) != rs.size:
        return []

    buckets: dict[str, float] = {}
    order: list[str] = []
    for d, r in zip(ds, rs):
        key = str(d)[:7]
        if key not in buckets:
            buckets[key] = 1.0
            order.append(key)
        buckets[key] *= 1.0 + float(r)

    return [
        {"month": k, "return_pct": round((buckets[k] - 1.0) * 100.0, 4)}
        for k in order
    ]


@dataclass
class RiskLimits:
    """风控硬阈值。默认值对齐 A 股单标的 CTA 的保守设定。"""

    max_position_pct: float = 100.0
    max_var_95_pct: float = 5.0
    max_drawdown_pct: float = 25.0
    max_annual_volatility_pct: float = 60.0
    min_samples: int = 20
    require_positive_return: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def evaluate_risk_gate(
    metrics: dict[str, Any],
    *,
    max_position_pct: float | None = None,
    limits: RiskLimits | None = None,
) -> dict[str, Any]:
    """确定性风控闸门：逐条检查硬规则，任一不过即拒绝（一票否决）。

    与 LLM 判断的分工：
      - 本函数只做**可复现的布尔判定**，不做"市场环境好不好"这类主观判断。
      - 拒绝原因逐条返回，便于审计与前端展示。
    """
    lim = limits or RiskLimits()
    reasons: list[str] = []
    checks: list[dict[str, Any]] = []

    def _check(name: str, value: Any, threshold: Any, passed: bool, desc: str) -> None:
        checks.append(
            {
                "rule": name,
                "value": value,
                "threshold": threshold,
                "passed": bool(passed),
                "desc": desc,
            }
        )
        if not passed:
            reasons.append(f"{desc}（实际 {value}，阈值 {threshold}）")

    # 退化序列（无交易/无有效波动）不可作为可交易结论通过
    if metrics.get("degenerate"):
        _check(
            "non_degenerate",
            metrics.get("degenerate_reason") or "degenerate",
            "有效波动",
            False,
            "收益序列无有效波动，无法评估风险",
        )

    samples = int(metrics.get("samples") or 0)
    _check(
        "min_samples",
        samples,
        lim.min_samples,
        samples >= lim.min_samples,
        "样本量不足，绩效指标不可信",
    )

    dd = abs(float(metrics.get("max_drawdown_pct") or 0.0))
    _check(
        "max_drawdown",
        round(dd, 4),
        lim.max_drawdown_pct,
        dd <= lim.max_drawdown_pct,
        "最大回撤超过风控上限",
    )

    var95 = float(metrics.get("var_95_pct") or 0.0)
    _check(
        "var_95",
        round(var95, 4),
        lim.max_var_95_pct,
        var95 <= lim.max_var_95_pct,
        "单日 VaR(95%) 超过风险预算",
    )

    vol = float(metrics.get("annual_volatility_pct") or 0.0)
    _check(
        "annual_volatility",
        round(vol, 4),
        lim.max_annual_volatility_pct,
        vol <= lim.max_annual_volatility_pct,
        "年化波动率超过上限",
    )

    if max_position_pct is not None:
        _check(
            "max_position",
            round(float(max_position_pct), 4),
            lim.max_position_pct,
            float(max_position_pct) <= lim.max_position_pct,
            "最大持仓占权益比超过上限",
        )

    if lim.require_positive_return:
        ret = float(metrics.get("total_return_pct") or 0.0)
        _check(
            "positive_return",
            round(ret, 4),
            0.0,
            ret > 0.0,
            "区间总收益为负",
        )

    approved = len(reasons) == 0
    return {
        "approved": approved,
        "verdict": "APPROVE" if approved else "REJECT",
        "reasons": reasons,
        "checks": checks,
        "limits": {
            "max_position_pct": lim.max_position_pct,
            "max_var_95_pct": lim.max_var_95_pct,
            "max_drawdown_pct": lim.max_drawdown_pct,
            "max_annual_volatility_pct": lim.max_annual_volatility_pct,
            "min_samples": lim.min_samples,
        },
    }


def position_exposure_summary(result_df: Any, size: float = 1.0) -> dict[str, Any]:
    """从 vn.py 逐日盯市 DataFrame 汇总仓位暴露。

    名义敞口 = |end_pos| × close_price × size；占权益比 = 敞口 / balance。
    返回最大值、均值、有仓天数占比——用于回答"这个策略是不是长期满仓"。
    """
    if result_df is None or getattr(result_df, "empty", True):
        return {
            "max_position_pct": 0.0,
            "avg_position_pct": 0.0,
            "exposure_days_ratio": 0.0,
            "days": 0,
        }

    pcts: list[float] = []
    holding = 0
    for _, row in result_df.iterrows():
        end_pos = abs(float(row.get("end_pos", 0) or 0))
        close_p = float(row.get("close_price", 0) or 0)
        balance = float(row.get("balance", 0) or 0)
        if end_pos > 0:
            holding += 1
        if balance > 1e-9:
            pcts.append(end_pos * close_p * float(size) / balance * 100.0)

    if not pcts:
        return {
            "max_position_pct": 0.0,
            "avg_position_pct": 0.0,
            "exposure_days_ratio": 0.0,
            "days": 0,
        }

    return {
        "max_position_pct": round(max(pcts), 4),
        "avg_position_pct": round(sum(pcts) / len(pcts), 4),
        "exposure_days_ratio": round(holding / len(pcts), 4),
        "days": len(pcts),
    }
