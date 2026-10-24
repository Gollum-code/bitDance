"""因子有效性分析：IC / RankIC / IC_IR / 分组收益（纯函数）。

选股器目前用固定权重打分（动量 25%、趋势 20%……），但这些权重是拍脑袋定的。
本模块回答一个更基础的问题：**这些因子在本市场样本里到底有没有预测力？**

口径：
  - IC：因子值与未来收益的 Pearson 相关
  - RankIC：Spearman 秩相关（对异常值更稳健，量化里更常用）
  - IC_IR：IC 均值 / IC 标准差，衡量预测力的稳定性
  - 分组收益：按因子值分 N 组，看未来收益是否单调

全部纯函数，输入 numpy，方便单测。
"""

from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np


def forward_returns(close: np.ndarray, horizon: int) -> np.ndarray:
    """由收盘价计算未来 horizon 期收益，末 horizon 个位置为 nan。"""
    arr = np.asarray(close, dtype=float)
    out = np.full(arr.size, np.nan)
    if arr.size <= horizon:
        return out
    with np.errstate(divide="ignore", invalid="ignore"):
        out[:-horizon] = arr[horizon:] / arr[:-horizon] - 1.0
    return out


def _rankdata(x: np.ndarray) -> np.ndarray:
    """平均秩（处理并列值），等价于 scipy.stats.rankdata(method='average')。"""
    arr = np.asarray(x, dtype=float)
    order = np.argsort(arr, kind="mergesort")
    ranks = np.empty(arr.size, dtype=float)
    i = 0
    while i < arr.size:
        j = i
        while j + 1 < arr.size and arr[order[j + 1]] == arr[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        ranks[order[i:j + 1]] = avg
        i = j + 1
    return ranks


def _pearson(x: np.ndarray, y: np.ndarray) -> float | None:
    if x.size < 2 or y.size != x.size:
        return None
    sx = float(np.std(x))
    sy = float(np.std(y))
    if sx < 1e-12 or sy < 1e-12:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def information_coefficient(
    factor: Iterable[float],
    fwd_return: Iterable[float],
    *,
    method: str = "rank",
) -> float | None:
    """单期 IC。method='rank' 返回 Spearman（默认），'pearson' 返回线性相关。"""
    f = np.asarray(list(factor), dtype=float)
    r = np.asarray(list(fwd_return), dtype=float)
    mask = np.isfinite(f) & np.isfinite(r)
    f, r = f[mask], r[mask]
    if f.size < 3:
        return None
    if method == "pearson":
        return _pearson(f, r)
    return _pearson(_rankdata(f), _rankdata(r))


def ic_statistics(ic_series: Iterable[float]) -> dict[str, Any]:
    """由多期 IC 序列汇总：均值、标准差、IC_IR、t 值、胜率。"""
    arr = np.asarray([v for v in ic_series if v is not None and math.isfinite(float(v))], dtype=float)
    n = arr.size
    if n == 0:
        return {
            "periods": 0,
            "ic_mean": None,
            "ic_std": None,
            "ic_ir": None,
            "t_stat": None,
            "positive_ratio": None,
            "latest_ic": None,
        }
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    ir = (mean / std) if std > 1e-12 else 0.0
    t_stat = ir * math.sqrt(n) if std > 1e-12 else 0.0
    return {
        "periods": n,
        "ic_mean": round(mean, 4),
        "ic_std": round(std, 4),
        "ic_ir": round(ir, 4),
        "t_stat": round(t_stat, 3),
        "positive_ratio": round(float(np.mean(arr > 0)), 4),
        "latest_ic": round(float(arr[-1]), 4),
    }


def quantile_returns(
    factor: Iterable[float],
    fwd_return: Iterable[float],
    *,
    quantiles: int = 5,
) -> dict[str, Any]:
    """按因子值分组，返回各组平均未来收益与多空价差。

    单调性（monotonicity）= 各组收益与组序号的秩相关，
    接近 ±1 说明因子方向稳定，接近 0 说明分组没有区分度。
    """
    f = np.asarray(list(factor), dtype=float)
    r = np.asarray(list(fwd_return), dtype=float)
    mask = np.isfinite(f) & np.isfinite(r)
    f, r = f[mask], r[mask]
    n = f.size
    q = max(2, min(int(quantiles), n // 2 if n >= 4 else 2))
    if n < q * 2:
        return {"ok": False, "reason": f"样本 {n} 个，不足以分 {q} 组"}

    order = np.argsort(f, kind="mergesort")
    groups = np.array_split(order, q)
    rets = [float(np.mean(r[g])) if g.size else 0.0 for g in groups]
    spread = rets[-1] - rets[0]

    # 单调性：组序号 vs 组收益的 Spearman
    mono = information_coefficient(np.arange(q), np.array(rets), method="rank") or 0.0

    return {
        "ok": True,
        "quantiles": q,
        "group_returns_pct": [round(v * 100, 4) for v in rets],
        "long_short_spread_pct": round(spread * 100, 4),
        "monotonicity": round(float(mono), 4),
        "direction": "positive" if spread > 0 else ("negative" if spread < 0 else "flat"),
    }


def summarize_factor(
    ic_values: Iterable[float],
    *,
    quantile_spreads: Iterable[float] | None = None,
) -> dict[str, Any]:
    """把一个因子的多期 IC 汇总成可直接展示的结论。"""
    stats = ic_statistics(ic_values)
    ir = stats.get("ic_ir")
    mean = stats.get("ic_mean")
    verdict = "insufficient"
    if isinstance(ir, (int, float)) and isinstance(mean, (int, float)):
        if abs(mean) >= 0.03 and abs(ir) >= 0.3:
            verdict = "effective"
        elif abs(mean) >= 0.02:
            verdict = "weak"
        else:
            verdict = "ineffective"

    labels = {
        "effective": "有效",
        "weak": "偏弱",
        "ineffective": "无效",
        "insufficient": "样本不足",
    }
    spreads = [float(s) for s in (quantile_spreads or []) if s is not None and math.isfinite(float(s))]
    return {
        **stats,
        "quantile_spread_avg_pct": round(float(np.mean(spreads)), 4) if spreads else None,
        "verdict": verdict,
        "verdict_label": labels[verdict],
    }
