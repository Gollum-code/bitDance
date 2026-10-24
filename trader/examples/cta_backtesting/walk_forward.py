"""前向验证（Walk-forward）与参数稳定性分析（纯函数 + 轻量回测驱动）。

要解决的问题：全区间参数寻优挑出来的「夏普最高」，往往是 in-sample 过拟合。
本模块把区间切成若干 train/test 段，**只在 train 上选参数，到 test 上看表现**，
输出样本外的一致性与参数稳健度，让「策略能用」这个结论可辩护。

设计：
  - 区间切分与折索引计算是纯函数（split_walk_forward），可单测。
  - 实际跑回测由回调注入（run_fn），本模块不依赖 vn.py，测试用假回测桩。
  - 结果汇总为效率比 / 一致性 / 过拟合概率等可读指标。
"""

from __future__ import annotations

import math
from typing import Any, Callable, Iterable, Sequence

import numpy as np

TRADING_DAYS = 252


def split_walk_forward(
    start: str,
    end: str,
    *,
    n_splits: int = 4,
    train_ratio: float = 0.7,
    embargo_days: int = 5,
) -> list[dict[str, str]]:
    """把 [start, end] 切成 n_splits 段，每段再分 train/test。

    切分方式：**滚动（rolling）**而非扩展（expanding）窗口——
      段 i 的 train 占前 train_ratio，test 占后 1-train_ratio；
      下一段从上一段起点向后平移一个段长。

    embargo_days：train 末尾与 test 开头之间剔除的交易日数，
    避免信息泄漏（尤其是用重叠窗口算因子/标签的场景）。

    纯函数，只做日期算术，不碰数据库。
    """
    import pandas as pd

    s = pd.Timestamp(start).normalize()
    e = pd.Timestamp(end).normalize()
    if e <= s:
        raise ValueError("end 必须晚于 start")

    n_splits = max(2, min(int(n_splits), 12))
    total_days = (e - s).days
    seg_days = total_days / n_splits
    if seg_days < 60:
        raise ValueError(f"区间过短（{total_days} 天），至少需要 {n_splits * 60} 天")

    folds: list[dict[str, str]] = []
    for i in range(n_splits):
        seg_start = s + pd.Timedelta(days=round(seg_days * i))
        seg_end = e if i == n_splits - 1 else s + pd.Timedelta(days=round(seg_days * (i + 1)))
        span = (seg_end - seg_start).days
        cut = seg_start + pd.Timedelta(days=round(span * train_ratio))
        # embargo：train 末尾再往前留出空档；test 从 cut 开始，train 到 cut-1 结束
        train_end = min(cut - pd.Timedelta(days=1), seg_end)
        test_start = min(cut + pd.Timedelta(days=max(0, embargo_days)), seg_end)
        if train_end < seg_start or test_start > seg_end:
            continue
        if test_start <= train_end:
            continue
        folds.append({
            "fold": i,
            "train_start": seg_start.strftime("%Y-%m-%d"),
            "train_end": train_end.strftime("%Y-%m-%d"),
            "test_start": test_start.strftime("%Y-%m-%d"),
            "test_end": seg_end.strftime("%Y-%m-%d"),
        })
    if not folds:
        raise ValueError("切分后无有效折，请缩短 embargo_days 或减少 n_splits")
    return folds


def _score_of(cell: dict, objective: str) -> float | None:
    """从回测结果里取目标分数。支持 sharpe / total_return / calmar。"""
    if not isinstance(cell, dict) or not cell.get("ok"):
        return None
    if objective == "total_return":
        v = cell.get("total_return")
        return float(v) if isinstance(v, (int, float)) and math.isfinite(float(v)) else None
    if objective == "calmar":
        v = cell.get("calmar")
        return float(v) if isinstance(v, (int, float)) and math.isfinite(float(v)) else None
    v = cell.get("sharpe")
    return float(v) if isinstance(v, (int, float)) and math.isfinite(float(v)) else None


def run_walk_forward(
    param_grid: Sequence[dict],
    *,
    start: str,
    end: str,
    run_fn: Callable[[dict, str, str], dict],
    n_splits: int = 4,
    train_ratio: float = 0.7,
    embargo_days: int = 5,
    objective: str = "sharpe",
    apply_risk_gate: bool = True,
    progress: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """执行 walk-forward 验证。

    参数
    ----
    param_grid : 候选参数列表，如 [{"fast_window": 5}, {"fast_window": 10}, ...]
    run_fn     : (params, start, end) -> 回测结果 dict。
                 需含 ok / sharpe / total_return / calmar / total_return /
                 max_drawdown / trade_count / risk_metrics 等字段（复用 analytics._run_backtest 形状）。
    objective  : 折内选参目标。

    流程
    ----
    for each fold:
        1. 在 train 段跑全部候选参数，按 objective 选最优（可选风控闸门过滤）
        2. 用该参数在 test 段跑一次，记录样本外表现
    汇总所有折的样本外结果 → 拼接成一条 OOS 收益曲线 → 计算指标

    返回
    ----
    {
      "folds": [每折详情],
      "oos": {样本外汇总指标},
      "in_sample_best": {各折 in-sample 最优点},
      "efficiency_ratio": 样本外/样本内 表现比（<0.5 视为明显退化）,
      "consistency": 样本外得分>0 的折占比,
      "overfit_probability": 由退化程度映射的 0~1 估计,
      "verdict": 文字结论,
    }
    """
    folds = split_walk_forward(
        start, end,
        n_splits=n_splits, train_ratio=train_ratio, embargo_days=embargo_days,
    )
    if not param_grid:
        return {"ok": False, "reason": "param_grid 为空", "folds": []}

    fold_reports: list[dict[str, Any]] = []
    oos_returns: list[float] = []
    oos_dates: list[str] = []
    in_sample_scores: list[float] = []

    for f in folds:
        # 1) train 段选参
        scored: list[tuple[dict, float, dict]] = []
        for params in param_grid:
            try:
                cell = run_fn(dict(params), f["train_start"], f["train_end"])
            except Exception as exc:  # 单组参数失败不影响整折
                cell = {"ok": False, "error": str(exc)}
            if progress is not None:
                progress(1, f"fold {f['fold']} train {params}")
            s = _score_of(cell, objective)
            if s is None:
                continue
            if apply_risk_gate:
                gate = ((cell.get("risk_metrics") or {}).get("risk_gate") or {})
                if gate and not gate.get("approved", True):
                    continue
            scored.append((params, s, cell))

        if not scored:
            fold_reports.append({
                **f,
                "ok": False,
                "reason": "train 段无有效候选参数（可能无行情数据或全被风控闸门过滤）",
            })
            continue

        scored.sort(key=lambda t: t[1], reverse=True)
        best_params, best_score, best_cell = scored[0]
        in_sample_scores.append(best_score)

        # 2) test 段验证
        try:
            oos = run_fn(dict(best_params), f["test_start"], f["test_end"])
        except Exception as exc:
            oos = {"ok": False, "error": str(exc)}
        if progress is not None:
            progress(1, f"fold {f['fold']} test")

        oos_score = _score_of(oos, objective)
        oos_ret = oos.get("total_return")
        if isinstance(oos_ret, (int, float)) and math.isfinite(float(oos_ret)):
            oos_returns.append(float(oos_ret))

        fold_reports.append({
            **f,
            "ok": bool(oos.get("ok")),
            "best_params": best_params,
            "in_sample_score": round(float(best_score), 4),
            "in_sample_return": best_cell.get("total_return"),
            "in_sample_sharpe": best_cell.get("sharpe"),
            "oos_params": best_params,
            "oos_score": None if oos_score is None else round(float(oos_score), 4),
            "oos_return": oos_ret if isinstance(oos_ret, (int, float)) else None,
            "oos_sharpe": oos.get("sharpe"),
            "oos_max_drawdown": oos.get("max_drawdown"),
            "oos_trade_count": oos.get("trade_count"),
            "degradation": (
                round((float(best_score) - oos_score) / (abs(float(best_score)) or 1.0), 4)
                if oos_score is not None else None
            ),
            "candidates": len(scored),
        })

    valid = [f for f in fold_reports if f.get("ok") and f.get("oos_score") is not None]
    if not valid:
        return {
            "ok": False,
            "reason": "所有折的样本外验证失败，请确认区间内已有行情数据",
            "folds": fold_reports,
        }

    is_avg = float(np.mean(in_sample_scores)) if in_sample_scores else 0.0
    oos_scores = [float(f["oos_score"]) for f in valid]
    oos_avg = float(np.mean(oos_scores))
    consistency = float(np.mean([1.0 if s > 0 else 0.0 for s in oos_scores]))

    denom = abs(is_avg) if abs(is_avg) > 1e-9 else 1.0
    efficiency = oos_avg / denom
    # 过拟合概率估计：完全退化(efficiency=0) → 1.0；等于或超过样本内 → 0.0
    overfit_prob = float(min(max(1.0 - efficiency, 0.0), 1.0))

    if efficiency < 0.5:
        verdict = (
            f"样本外效率比 {efficiency:.2f}（样本内 {is_avg:.3f} → 样本外 {oos_avg:.3f}），"
            "参数过拟合明显，当前寻优结果不可信，建议减少参数维度或拉长样本区间。"
        )
    elif efficiency < 0.8:
        verdict = (
            f"样本外效率比 {efficiency:.2f}，存在一定退化但在可接受范围，"
            "建议优先取邻域稳健参数而非最优点。"
        )
    else:
        verdict = (
            f"样本外效率比 {efficiency:.2f}，样本内外表现一致，参数选择具备可迁移性。"
        )

    return {
        "ok": True,
        "objective": objective,
        "n_splits": len(folds),
        "train_ratio": train_ratio,
        "embargo_days": embargo_days,
        "folds": fold_reports,
        "in_sample_avg": round(is_avg, 4),
        "oos_avg": round(oos_avg, 4),
        "oos_returns_pct": [round(r, 4) for r in oos_returns],
        "efficiency_ratio": round(efficiency, 4),
        "consistency": round(consistency, 4),
        "overfit_probability": round(overfit_prob, 4),
        "apply_risk_gate": apply_risk_gate,
        "verdict": verdict,
        "message": (
            f"{len(valid)}/{len(folds)} 折通过样本外验证 · 效率比 {efficiency:.2f} · "
            f"一致性 {consistency:.0%}"
        ),
    }
