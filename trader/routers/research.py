"""研究类路由：前向验证（walk-forward）、参数稳定性、因子有效性（IC/IR）。

这三个端点回答的是「能不能信」而不是「赚了多少」：
  - /analytics/walk-forward：把区间切 train/test，只在 train 选参数，看样本外表现
  - /analytics/stability：参数曲面是否孤立尖峰（过拟合检测）
  - /analytics/factor-ic：选股用的因子到底有没有预测力

复用 analytics._run_backtest（同一 vn.py 回测引擎）与 free_market 行情源。
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from examples.cta_backtesting.factor_ic import (
    forward_returns,
    information_coefficient,
    quantile_returns,
    summarize_factor,
)
from examples.cta_backtesting.monte_carlo import parameter_stability
from examples.cta_backtesting.walk_forward import run_walk_forward
from routers import analytics
from routers.free_market import fetch_stock_list as free_list

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_GRID = 24          # 候选参数上限（每折都要跑，控制总耗时）
MAX_SYMBOLS = 20       # 因子 IC 分析标的数上限


# ---- 前向验证 ----


class WalkForwardRequest(BaseModel):
    strategy_id: str = Field(..., description="策略 id")
    param_name: str = Field("fast_window", description="要寻优的参数名（策略 parameters 之一）")
    values: list[float] = Field(..., description="候选参数取值，如 [5,10,15,20,25]")
    vt_symbol: str = "600519.SSE"
    start: str = "2021-01-01"
    end: str | None = None
    capital: int = 10_000
    n_splits: int = Field(4, ge=2, le=8, description="切分折数")
    train_ratio: float = Field(0.7, ge=0.5, le=0.9)
    embargo_days: int = Field(5, ge=0, le=30, description="train/test 之间的空档天数，防信息泄漏")
    objective: str = Field("sharpe", description="折内选参目标：sharpe / total_return / calmar")
    fixed_params: dict[str, float] | None = None
    apply_risk_gate: bool = True


def _cell_shape(cell: dict) -> dict:
    """把 _run_backtest 结果裁剪成 walk_forward 需要的形状。"""
    if not cell.get("ok"):
        return {"ok": False, "error": cell.get("error", "回测失败")}
    st = cell.get("stats") or {}
    rm = ((cell.get("risk_metrics") or {}).get("risk_metrics") or {})
    return {
        "ok": True,
        "sharpe": cell.get("sharpe", st.get("sharpe_ratio")),
        "total_return": st.get("total_return"),
        "calmar": rm.get("calmar_ratio"),
        "max_drawdown": st.get("max_drawdown"),
        "trade_count": cell.get("trade_count", 0),
        "risk_metrics": cell.get("risk_metrics") or {},
    }


@router.post("/walk-forward")
def walk_forward(body: WalkForwardRequest):
    return _walk_forward_impl(body)


def _walk_forward_impl(body: WalkForwardRequest, progress=None, cancelled=None):
    """滚动前向验证：每折只在 train 段选参数，到 test 段看样本外表现。

    输出效率比（样本外/样本内）、一致性、过拟合概率估计。
    """
    values = [float(v) for v in body.values]
    if len(values) < 2:
        raise HTTPException(status_code=400, detail="至少提供 2 个候选参数")
    if len(values) > MAX_GRID:
        raise HTTPException(status_code=400, detail=f"候选参数上限 {MAX_GRID} 个（当前 {len(values)}）")
    if body.objective not in ("sharpe", "total_return", "calmar"):
        raise HTTPException(status_code=400, detail="objective 仅支持 sharpe / total_return / calmar")

    end = body.end or date.today().isoformat()
    sid = body.strategy_id.zfill(2)
    cfg_base: dict[str, Any] = {
        "vt_symbol": body.vt_symbol,
        "capital": body.capital,
    }
    if body.fixed_params:
        cfg_base.update(body.fixed_params)

    grid = [{body.param_name: (int(v) if float(v).is_integer() else v)} for v in values]

    def run_fn(params: dict, start_d: str, end_d: str) -> dict:
        if cancelled is not None and cancelled():
            raise analytics.JobCancelled()
        cfg = {**cfg_base, "start": start_d, "end": end_d, **params}
        try:
            # walk-forward 每个候选参数都要跑，跳过 bootstrap 以控制总耗时
            raw = analytics._run_backtest(sid, cfg, include_monte_carlo=False)
        except Exception as exc:  # 单次回测失败不应中断整条验证链
            logger.warning("walk-forward 回测失败 %s-%s: %r", start_d, end_d, exc)
            return {"ok": False, "error": str(exc)}
        return _cell_shape(raw)

    try:
        out = run_walk_forward(
            grid,
            start=body.start,
            end=end,
            run_fn=run_fn,
            n_splits=body.n_splits,
            train_ratio=body.train_ratio,
            embargo_days=body.embargo_days,
            objective=body.objective,
            apply_risk_gate=body.apply_risk_gate,
            progress=progress,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        **out,
        "strategy_id": sid,
        "param_name": body.param_name,
        "values": values,
        "vt_symbol": body.vt_symbol,
        "start": body.start,
        "end": end,
        "class_name": _resolve_class_name(sid),
    }


def _resolve_class_name(sid: str) -> str | None:
    try:
        from examples.cta_backtesting.run_rewritten_strategy_backtest import load_strategy_class

        _, row = load_strategy_class(sid.zfill(2))
        return row.get("class_name")
    except Exception:
        return None


# ---- 参数稳定性 / 过拟合检测 ----


class StabilityRequest(BaseModel):
    strategy_id: str
    param_name: str = "fast_window"
    values: list[float] = Field(..., description="已扫描的参数取值列表")
    objective: str = Field("sharpe", description="sharpe / total_return / calmar")
    vt_symbol: str = "600519.SSE"
    start: str = "2024-01-01"
    end: str | None = None
    capital: int = 10_000
    neighbor_ratio: float = Field(0.6, ge=0.1, le=2.0, description="孤立尖峰判定阈值")
    fixed_params: dict[str, float] | None = None


@router.post("/stability")
def param_stability(body: StabilityRequest):
    """参数曲面平滑度分析：最优参数是否孤立尖峰。

    与 /analytics/grid 的分工：grid 给「哪个参数最好」，
    本接口给「这个最好能不能信」。建议先用 grid 扫描，
    再把 cells 的 value/score 喂给本接口。
    """
    if len(body.values) < 3:
        raise HTTPException(status_code=400, detail="至少需要 3 个参数点才能评估稳定性")
    if body.objective not in ("sharpe", "total_return", "calmar"):
        raise HTTPException(status_code=400, detail="objective 仅支持 sharpe / total_return / calmar")

    end = body.end or date.today().isoformat()
    sid = body.strategy_id.zfill(2)
    cfg_base: dict[str, Any] = {"vt_symbol": body.vt_symbol, "capital": body.capital}
    if body.fixed_params:
        cfg_base.update(body.fixed_params)

    scores: list[float] = []
    for v in body.values:
        p = (int(v) if float(v).is_integer() else v)
        try:
            cell = _cell_shape(
                analytics._run_backtest(
                    sid,
                    {**cfg_base, "start": body.start, "end": end, body.param_name: p},
                    include_monte_carlo=False,
                )
            )
        except Exception as exc:
            logger.warning("stability 回测失败 %s=%s: %r", body.param_name, p, exc)
            cell = {"ok": False}
        scores.append(_objective_value(cell, body.objective))

    out = parameter_stability(
        body.values, scores, objective=body.objective, neighbor_ratio=body.neighbor_ratio
    )
    return {
        **out,
        "strategy_id": sid,
        "class_name": _resolve_class_name(sid),
        "param_name": body.param_name,
        "vt_symbol": body.vt_symbol,
        "start": body.start,
        "end": end,
    }


def _objective_value(cell: dict, objective: str) -> float | None:
    if not cell.get("ok"):
        return None
    if objective == "total_return":
        v = cell.get("total_return")
    elif objective == "calmar":
        v = cell.get("calmar")
    else:
        v = cell.get("sharpe")
    if isinstance(v, (int, float)) and np.isfinite(float(v)):
        return float(v)
    return None


# ---- 因子有效性（IC / IR） ----


class FactorIcRequest(BaseModel):
    vt_symbols: list[str] = Field(..., description="标的列表（vn.py 格式），建议 10-20 个")
    factor: str = Field(
        "momentum",
        description="momentum / trend / ma_bias / volatility / vol_ratio / amihud / drawdown_from_high",
    )
    horizon: int = Field(20, ge=1, le=120, description="未来收益 horizon（交易日）")
    lookback_days: int = Field(120, ge=40, le=400)
    end_date: str | None = None


@router.post("/factor-ic")
def factor_ic(body: FactorIcRequest):
    """计算单个因子的横截面 IC / RankIC / IC_IR / 分组收益。

    做法：在多个时间截面上，对一组标的算因子值与未来 horizon 收益，
    逐期算 RankIC，再汇总成 IC_IR。需要足够的截面样本（标的数 × 期数）。
    """
    symbols = [str(s).strip() for s in body.vt_symbols if str(s).strip()][:MAX_SYMBOLS]
    if len(symbols) < 5:
        raise HTTPException(status_code=400, detail=f"至少需要 5 个标的做横截面（当前 {len(symbols)}）")

    end_date = body.end_date or date.today().isoformat()
    end_d = pd.Timestamp(end_date)
    # 需要 lookback 算因子 + horizon 算未来收益，取数范围向后多留
    start_d = (end_d - pd.Timedelta(days=int(body.lookback_days * 2.2))).strftime("%Y-%m-%d")

    series_map: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = analytics._load_daily_df(sym, start_d, end_d.strftime("%Y-%m-%d"))
        if df is not None and len(df) >= max(40, body.lookback_days // 2):
            series_map[sym] = df.sort_values("trade_date").reset_index(drop=True)

    if len(series_map) < 5:
        raise HTTPException(status_code=502, detail=f"仅 {len(series_map)} 个标的数据充足，无法做横截面分析")

    # 逐标的算因子序列 + 未来收益序列
    factor_series: dict[str, np.ndarray] = {}
    fwd_series: dict[str, np.ndarray] = {}
    for sym, df in series_map.items():
        close = df["close"].astype(float).to_numpy()
        fwd = forward_returns(close, body.horizon)
        fac = _factor_series(df, body.factor, body.lookback_days)
        if fac is None:
            continue
        n = min(len(fac), len(fwd))
        factor_series[sym] = fac[:n]
        fwd_series[sym] = fwd[:n]

    if len(factor_series) < 5:
        raise HTTPException(status_code=502, detail="因子计算后可用标的不足 5 个")

    # 逐截面算 RankIC：只在所有标的都有未来收益的日期上取截面
    common_dates = None
    for sym, fac in factor_series.items():
        valid = np.isfinite(fac) & np.isfinite(fwd_series[sym])
        idx = set(np.where(valid)[0].tolist())
        common_dates = idx if common_dates is None else (common_dates & idx)
    dates = sorted(common_dates or [])
    if len(dates) < 5:
        raise HTTPException(status_code=502, detail=f"有效截面仅 {len(dates)} 期，无法计算 IC_IR（至少 5 期）")

    ic_series: list[float] = []
    for i in dates:
        fac_row = np.array([factor_series[s][i] for s in factor_series], dtype=float)
        fwd_row = np.array([fwd_series[s][i] for s in fwd_series], dtype=float)
        ic = information_coefficient(fac_row, fwd_row, method="rank")
        if ic is not None:
            ic_series.append(ic)

    if len(ic_series) < 5:
        raise HTTPException(status_code=502, detail=f"有效 IC 期数 {len(ic_series)} 过少")

    # 分组收益：用最后一期截面（当期因子 -> 未来收益）
    last = dates[-1]
    fac_row = np.array([factor_series[s][last] for s in factor_series], dtype=float)
    fwd_row = np.array([fwd_series[s][last] for s in fwd_series], dtype=float)
    q = quantile_returns(fac_row, fwd_row, quantiles=min(5, max(2, len(factor_series) // 2)))

    return {
        "success": True,
        "factor": body.factor,
        "horizon": body.horizon,
        "lookback_days": body.lookback_days,
        "symbols": list(factor_series.keys()),
        "periods": len(ic_series),
        "ic": summarize_factor(
            ic_series, quantile_spreads=[q.get("long_short_spread_pct")] if q.get("ok") else None
        ),
        "ic_series": [round(float(v), 4) for v in ic_series],
        "quantile": q,
        "message": (
            f"因子 {body.factor}（{len(factor_series)} 标的 × {len(ic_series)} 期）"
            f"RankIC 均值 {np.mean(ic_series):.4f}"
        ),
    }


def _factor_series(df: pd.DataFrame, name: str, lookback: int) -> np.ndarray | None:
    """逐日计算因子值序列（与 analytics._compute_factors 口径一致，只是逐日展开）。"""
    close = df["close"].astype(float).to_numpy()
    high = df["high"].astype(float).to_numpy()
    low = df["low"].astype(float).to_numpy()
    vol = df.get("vol")
    vol = vol.astype(float).to_numpy() if vol is not None else np.zeros(len(df))
    n = len(close)
    if n < 30:
        return None

    out = np.full(n, np.nan)
    for i in range(29, n):
        c = close[: i + 1]
        h = high[: i + 1]
        l = low[: i + 1]
        v = vol[: i + 1]
        try:
            if name == "momentum":
                lb = min(20, len(c))
                out[i] = c[-1] / c[-lb] - 1.0
            elif name == "trend":
                lb = min(60, len(c))
                out[i] = c[-1] / c[-lb:].mean() - 1.0
            elif name == "ma_bias":
                lb = min(20, len(c))
                out[i] = c[-1] / c[-lb:].mean() - 1.0
            elif name == "volatility":
                rets = np.diff(c)
                lb = min(60, len(rets))
                out[i] = float(np.std(rets[-lb:]) * np.sqrt(252)) if lb > 1 else np.nan
            elif name == "vol_ratio":
                ma20 = v[-20:].mean()
                out[i] = (v[-5:].mean() / ma20) if ma20 > 0 else np.nan
            elif name == "amihud":
                rets = np.diff(c)
                vv = v[1:]
                lb = min(20, len(rets))
                out[i] = float(np.mean(np.abs(rets[-lb:]) / (vv[-lb:] + 1e-9)))
            elif name == "drawdown_from_high":
                lb = min(60, len(c))
                hi = float(np.max(h[-lb:]))
                out[i] = (c[-1] / hi - 1.0) if hi > 0 else np.nan
            else:
                raise HTTPException(status_code=400, detail=f"未知因子: {name}")
        except Exception:
            continue
    return out


# ---- 因子快照（供因子 IC 页面选择标的用） ----


@router.get("/factor-universe")
def factor_universe(limit: int = 30):
    """取一篮子常用标的作为因子分析默认样本（茅台 + 各行业代表 + 指数权重股）。"""
    universe = [
        "600519.SSE", "000001.SZSE", "600036.SSE", "601318.SSE", "000858.SZSE",
        "600030.SSE", "002594.SZSE", "601899.SSE", "600900.SSE", "601166.SSE",
        "000002.SZSE", "600276.SSE", "601012.SSE", "600887.SSE", "000063.SZSE",
        "002415.SZSE", "600309.SSE", "601888.SSE", "000725.SZSE", "600000.SSE",
    ][: max(5, min(limit, MAX_SYMBOLS))]
    return {"symbols": universe, "count": len(universe)}
