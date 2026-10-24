"""蒙特卡洛 / Block Bootstrap 置信区间（纯函数）。

对已有日收益序列做重采样，回答点估计回答不了的问题：
  - 「夏普 1.2」是真的稳定，还是样本区间的运气？
  - 最大回撤的**分布**长什么样，而不是单个数字？
  - 再跑一次同样的策略，收益落在哪个区间的概率是 95%？

实现选择 **Block Bootstrap**（而非简单 IID 重采样）的原因：
金融日收益存在序列相关（趋势/均值回复），IID 重采样会打散这种结构，
得到的置信带过窄。按固定块长整体移动采样能保留局部相关性。

纯函数，不读写全局状态，可单测。`numpy` 随机源由调用方传入 seed 控制，
保证同输入同输出。
"""

from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np

TRADING_DAYS = 252
DEFAULT_BLOCK = 20          # 约一个月交易日，保留月度相关性
DEFAULT_SIMS = 2000


def block_bootstrap_returns(
    returns: Iterable[float],
    *,
    sims: int = DEFAULT_SIMS,
    block: int = DEFAULT_BLOCK,
    seed: int = 42,
) -> np.ndarray:
    """Block bootstrap 重采样，返回 (sims, n) 的重采样收益矩阵。

    做法：把原始序列按块长 `block` 切成若干段，随机有放回地抽取这些段，
    拼接成长度等于原序列的新序列。重复 sims 次。
    """
    arr = np.asarray(list(returns), dtype=float)
    arr = arr[~np.isnan(arr)]
    n = arr.size
    if n < 4:
        return np.zeros((0, max(n, 0)), dtype=float)

    block = max(1, min(int(block), n))
    n_blocks = int(math.ceil(n / block))
    # 起点集合不含最后一段：保证每个块都取到完整 block 长度
    starts = np.arange(0, n - block + 1) if n >= block else np.array([0])

    rng = np.random.default_rng(seed)
    out = np.empty((sims, n), dtype=float)
    for i in range(sims):
        pick = rng.choice(starts, size=n_blocks, replace=True)
        # 拼接：每块取 arr[s:s+block]；循环取块直到填满 n，再截断
        pieces: list[np.ndarray] = []
        total = 0
        for s in pick:
            if total >= n:
                break
            pieces.append(arr[s:s + block])
            total += block
        out[i] = np.concatenate(pieces)[:n]
    return out


def _stats_from_returns(rets: np.ndarray, risk_free: float = 0.02) -> dict[str, float]:
    """单条收益序列的绩效摘要（与 risk_metrics.compute_risk_metrics 同口径的年化/夏普）。"""
    n = rets.size
    if n == 0:
        return {"total_return": 0.0, "annual_return": 0.0, "sharpe": 0.0, "max_dd": 0.0}
    total = float(np.prod(1.0 + rets) - 1.0)
    annual = (1.0 + total) ** (TRADING_DAYS / n) - 1.0 if total > -1.0 else -1.0
    std = float(np.std(rets, ddof=1)) if n > 1 else 0.0
    vol = std * math.sqrt(TRADING_DAYS)
    sharpe = ((annual - risk_free) / vol) if vol > 1e-12 else 0.0
    nav = np.cumprod(1.0 + rets)
    peak = np.maximum.accumulate(nav)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = np.where(peak > 1e-12, nav / peak - 1.0, 0.0)
    dd = np.nan_to_num(dd, nan=0.0, posinf=0.0, neginf=0.0)
    return {
        "total_return": total,
        "annual_return": annual,
        "sharpe": sharpe,
        "max_dd": float(dd.min()) if dd.size else 0.0,
    }


def monte_carlo_summary(
    returns: Iterable[float],
    *,
    sims: int = DEFAULT_SIMS,
    block: int = DEFAULT_BLOCK,
    seed: int = 42,
    confidence: float = 0.95,
    risk_free: float = 0.02,
) -> dict[str, Any]:
    """对收益序列做 block bootstrap，输出关键指标的置信区间与分位数。

    返回结构（可直接进 JSON / 前端）：
      {
        "sims": int, "block": int, "confidence": float,
        "sample": {原始点估计},
        "total_return": {p05, p50, p95, mean, std, prob_positive},
        "annual_return": {...},
        "sharpe":       {...},
        "max_drawdown": {...},   # 注意：这是**深度的绝对值**，越大越糟
        "sharpe_ci": [lo, hi],   # 便捷字段
        "drawdown_p95": float,   # 95% 分位回撤深度，做仓位/风控预算用
      }

    样本不足（n<4）时返回 `{"ok": False, "reason": ...}`，由调用方降级。
    """
    arr = np.asarray(list(returns), dtype=float)
    arr = arr[~np.isnan(arr)]
    n = arr.size
    if n < 4:
        return {"ok": False, "reason": f"样本量 {n} 过少，无法做有意义的 bootstrap", "sims": 0}

    sims = int(max(100, min(sims, 20000)))
    matrix = block_bootstrap_returns(arr, sims=sims, block=block, seed=seed)

    total_r, annual_r, sharpes, dds = [], [], [], []
    for i in range(matrix.shape[0]):
        s = _stats_from_returns(matrix[i], risk_free=risk_free)
        total_r.append(s["total_return"])
        annual_r.append(s["annual_return"])
        sharpes.append(s["sharpe"])
        dds.append(abs(s["max_dd"]))

    def _ci(vals: list[float]) -> dict[str, Any]:
        a = np.asarray(vals, dtype=float)
        lo_q = (1.0 - confidence) / 2.0 * 100.0
        hi_q = (1.0 + confidence) / 2.0 * 100.0
        return {
            "p05": round(float(np.percentile(a, lo_q)), 4),
            "p50": round(float(np.percentile(a, 50.0)), 4),
            "p95": round(float(np.percentile(a, hi_q)), 4),
            "mean": round(float(np.mean(a)), 4),
            "std": round(float(np.std(a, ddof=1)) if a.size > 1 else 0.0, 4),
            "prob_positive": round(float(np.mean(a > 0)), 4),
        }

    point = _stats_from_returns(arr, risk_free=risk_free)

    lo_q = (1.0 - confidence) / 2.0 * 100.0
    hi_q = (1.0 + confidence) / 2.0 * 100.0

    # 置信带：逐日累计收益的 p05/p50/p95，用于前端画扇形图
    nav_paths = np.cumprod(1.0 + matrix, axis=1)
    band_lo = np.percentile(nav_paths, lo_q, axis=0) - 1.0
    band_mid = np.median(nav_paths, axis=0) - 1.0
    band_hi = np.percentile(nav_paths, hi_q, axis=0) - 1.0

    return {
        "ok": True,
        "sims": sims,
        "block": int(block),
        "confidence": confidence,
        "sample": {
            "total_return_pct": round(point["total_return"] * 100, 4),
            "annual_return_pct": round(point["annual_return"] * 100, 4),
            "sharpe": round(point["sharpe"], 4),
            "max_drawdown_pct": round(abs(point["max_dd"]) * 100, 4),
        },
        # 收益类指标
        "total_return": _ci([v * 100 for v in total_r]),
        "annual_return": _ci([v * 100 for v in annual_r]),
        # 风险类指标（回撤/夏普）
        "sharpe": _ci(sharpes),
        "max_drawdown": _ci([v * 100 for v in dds]),
        "sharpe_ci": [
            round(float(np.percentile(sharpes, lo_q)), 4),
            round(float(np.percentile(sharpes, hi_q)), 4),
        ],
        "drawdown_p95": round(float(np.percentile(dds, 95.0)) * 100, 4),
        # 置信带（累计收益 %），前端直接画
        "band": {
            "lo": [round(float(v) * 100, 4) for v in band_lo],
            "mid": [round(float(v) * 100, 4) for v in band_mid],
            "hi": [round(float(v) * 100, 4) for v in band_hi],
        },
        "interpretation": _interpret(point, sharpes, dds, confidence),
    }


def _interpret(point: dict, sharpes: list[float], dds: list[float], confidence: float) -> list[str]:
    """把统计结果翻译成人话，避免报告里只丢一堆分位数。"""
    notes: list[str] = []
    if not sharpes:
        return notes
    lo = float(np.percentile(sharpes, (1 - confidence) / 2 * 100))
    hi = float(np.percentile(sharpes, (1 + confidence) / 2 * 100))
    if lo <= 0.0 <= hi:
        notes.append(
            f"夏普的 {int(confidence * 100)}% 置信区间 [{lo:.2f}, {hi:.2f}] 跨越 0，"
            "说明当前样本无法排除「策略无风险调整后优势」的可能。"
        )
    else:
        notes.append(f"夏普的 {int(confidence * 100)}% 置信区间 [{lo:.2f}, {hi:.2f}] 不跨越 0。")

    dd95 = float(np.percentile(dds, 95.0)) * 100
    if dd95 > 0:
        notes.append(
            f"95% 分位最大回撤深度 {dd95:.2f}%——按此做仓位/风险预算比用单点最大回撤更稳健。"
        )
    if point["sharpe"] > hi:
        notes.append("原始点估计夏普高于 bootstrap 上界，可能存在样本特殊性，建议拉长样本区间复核。")
    return notes


def parameter_stability(
    param_values: Iterable[float],
    scores: Iterable[float],
    *,
    objective: str = "sharpe",
    neighbor_ratio: float = 0.6,
) -> dict[str, Any]:
    """参数曲面平滑度 / 过拟合风险检测。

    核心思想：真正稳健的策略，参数邻域内的表现应**平滑过渡**；
    如果最优参数是一个孤立尖峰（邻居表现断崖式下跌），
    大概率是过拟合——那个参数点只是恰好命中了样本噪声。

    输出：
      - best_param / best_score：最优点
      - neighbor_avg：最优参数左右邻居的均分
      - degradation：最优分相对邻居均分的提升幅度
      - isolated_peak：True 表示孤立尖峰（过拟合风险）
      - smoothness：相邻参数得分的平均绝对变化（越小越平滑）
      - verdict：文字结论
    """
    vals = [float(v) for v in param_values]
    scs = [float(s) for s in scores if s is not None]
    pairs = [(v, s) for v, s in zip(vals, scs) if s is not None and math.isfinite(s)]
    if len(pairs) < 3:
        return {
            "ok": False,
            "reason": f"有效参数点 {len(pairs)} 个，至少需要 3 个才能评估稳定性",
            "isolated_peak": False,
        }

    pairs.sort(key=lambda x: x[0])
    xs = np.array([p[0] for p in pairs])
    ys = np.array([p[1] for p in pairs])

    best_i = int(np.argmax(ys))
    best_param = float(xs[best_i])
    best_score = float(ys[best_i])

    # 邻居：取排序后左右各一个（边界处只有一个）
    neighbors: list[float] = []
    if best_i > 0:
        neighbors.append(float(ys[best_i - 1]))
    if best_i < len(ys) - 1:
        neighbors.append(float(ys[best_i + 1]))
    neighbor_avg = float(np.mean(neighbors)) if neighbors else best_score

    base = abs(neighbor_avg) if abs(neighbor_avg) > 1e-9 else 1.0
    degradation = (best_score - neighbor_avg) / base

    # 平滑度：相邻点得分的平均绝对跳变（归一化到极差，避免量纲影响）
    diffs = np.abs(np.diff(ys))
    span = float(np.max(ys) - np.min(ys))
    smoothness = float(np.mean(diffs) / span) if span > 1e-12 else 0.0

    isolated = degradation > neighbor_ratio and span > 1e-12

    if isolated:
        verdict = (
            f"孤立尖峰：最优 {objective}={best_score:.4f} 比邻居均值 {neighbor_avg:.4f} 高 "
            f"{degradation * 100:.1f}%，邻域表现断崖式下跌——过拟合风险高，不建议直接采用。"
        )
    elif degradation <= 0:
        verdict = (
            f"最优点 {objective}={best_score:.4f} 未超过邻居均值 {neighbor_avg:.4f}，"
            "参数曲面平坦，说明该参数对结果不敏感，可取下游更稳健的值。"
        )
    else:
        verdict = (
            f"参数曲面平滑：最优 {objective}={best_score:.4f} 较邻居均值 {neighbor_avg:.4f} "
            f"提升 {degradation * 100:.1f}%，未出现孤立尖峰。"
        )

    return {
        "ok": True,
        "objective": objective,
        "best_param": best_param,
        "best_score": round(best_score, 4),
        "neighbor_avg": round(neighbor_avg, 4),
        "degradation": round(degradation, 4),
        "smoothness": round(smoothness, 4),
        "isolated_peak": bool(isolated),
        "threshold": neighbor_ratio,
        "points": len(pairs),
        "curve": [
            {"param": round(float(p[0]), 6), "score": round(float(p[1]), 4)} for p in pairs
        ],
        "verdict": verdict,
    }
