"""分析类路由：多策略对比 / 因子选股 / 参数网格优化 / 实时行情推送。

复用现有回测引擎（examples.cta_backtesting.run_rewritten_strategy_backtest）
与免费行情源（routers.free_market），不重复造轮子。
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, WebSocket
from pydantic import BaseModel, Field

from examples.cta_backtesting.run_rewritten_strategy_backtest import (
    DEFAULT_CONFIG,
    build_setting,
    load_strategy_class,
    main as _run_backtest_main,
)
from examples.cta_backtesting.monte_carlo import monte_carlo_summary
from examples.cta_backtesting.risk_metrics import (
    RiskLimits,
    compute_risk_metrics,
    cumulative_to_returns,
    evaluate_risk_gate,
    monthly_returns,
    position_exposure_summary,
)
from routers.free_market import fetch_daily as free_daily
from routers.free_market import fetch_stock_list as free_list
from routers.job_store import JobCancelled, JobManager
from routers.market_data import ts_code_to_vt_symbol

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_COMPARE = 8
MAX_GRID_CELLS = 60
_grid_cache: dict[str, Any] = {}
_executor_pool: ThreadPoolExecutor | None = None
jobs = JobManager()


def _executor() -> ThreadPoolExecutor:
    global _executor_pool
    if _executor_pool is None:
        _executor_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="analytics")
    return _executor_pool


def _safe(v: Any) -> Any:
    """把 numpy / date 类型转成 JSON 可序列化的原生类型。"""
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, (date, pd.Timestamp)):
        return v.isoformat()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _run_backtest(sid: str, cfg: dict, include_monte_carlo: bool = True) -> dict:
    """执行单策略回测，返回 stats + series(权益曲线) + 交易数。不抛异常，失败用 ok=False。"""
    import sys as _sys

    from vnpy.trader.constant import Interval
    from vnpy_ctastrategy.backtesting import BacktestingEngine
    from examples.cta_backtesting.run_rewritten_strategy_backtest import parse_date

    # 确保 rewritten_strategies 包可导入（与 run_rewritten_strategy_backtest 相同做法）
    script_dir = Path(__file__).resolve().parent.parent / "examples" / "cta_backtesting"
    if str(script_dir) not in _sys.path:
        _sys.path.insert(0, str(script_dir))

    sid = sid.zfill(2)
    try:
        strategy_cls, row = load_strategy_class(sid)
    except Exception as e:
        return {"ok": False, "strategy_id": sid, "error": f"策略加载失败: {e}"}

    engine = BacktestingEngine()
    engine.set_parameters(
        vt_symbol=cfg["vt_symbol"],
        interval=Interval.DAILY,
        start=parse_date(cfg["start"]),
        end=parse_date(cfg["end"]),
        rate=cfg.get("rate", DEFAULT_CONFIG["rate"]),
        slippage=cfg.get("slippage", DEFAULT_CONFIG["slippage"]),
        size=cfg.get("size", DEFAULT_CONFIG["size"]),
        pricetick=cfg.get("pricetick", DEFAULT_CONFIG["pricetick"]),
        capital=cfg.get("capital", DEFAULT_CONFIG["capital"]),
    )
    overrides = {k: cfg.get(k) for k in getattr(strategy_cls, "parameters", []) if cfg.get(k) is not None}
    setting = build_setting(strategy_cls, row, overrides)
    engine.add_strategy(strategy_cls, setting)
    engine.load_data()
    if not engine.history_data:
        return {"ok": False, "strategy_id": sid, "class_name": row["class_name"], "error": "本地库无该标的日线数据，请先同步"}

    engine.run_backtesting()
    result_df = engine.calculate_result()
    stats = engine.calculate_statistics()

    series = {"dates": [], "balance": []}
    first_close = None
    if result_df is not None and not result_df.empty:
        series["dates"] = [i.strftime("%Y-%m-%d") if hasattr(i, "strftime") else str(i) for i in result_df.index]
        if "balance" in result_df.columns:
            series["balance"] = [float(v) for v in result_df["balance"].fillna(0).tolist()]
        if "close_price" in result_df.columns:
            series["close"] = [float(v) for v in result_df["close_price"].fillna(0).tolist()]
            if series["close"]:
                first_close = series["close"][0]

    # 归一化为百分比收益，便于多策略叠加对比
    norm = []
    if series["balance"] and series["balance"][0] > 0:
        base = series["balance"][0]
        norm = [round((b / base - 1) * 100, 4) for b in series["balance"]]

    return {
        "ok": True,
        "strategy_id": sid,
        "class_name": row["class_name"],
        "archetype": row["archetype"],
        "stats": {k: _safe(v) for k, v in stats.items()},
        "trade_count": len(engine.trades),
        "series": {"dates": series["dates"], "returns": norm},
        "first_close": first_close,
        "risk_metrics": _risk_block(
            series["dates"], norm, engine.daily_df, float(cfg.get("size", 1)),
            include_monte_carlo=include_monte_carlo,
        ),
    }


def _risk_block(dates: list, returns: list, daily_df: Any, size: float, *, include_monte_carlo: bool = True) -> dict:
    """由权益曲线 + 逐日盯市表计算风险指标、月度收益与风控闸门结论。

    失败时返回空 dict，不影响主回测结果返回。
    """
    if not dates or not returns:
        return {}
    try:
        rets = cumulative_to_returns(returns)
        metrics = compute_risk_metrics(rets)
        exposure = position_exposure_summary(daily_df, size)
        metrics["max_position_pct"] = exposure["max_position_pct"]
        metrics["avg_position_pct"] = exposure["avg_position_pct"]
        metrics["exposure_days_ratio"] = exposure["exposure_days_ratio"]
        out: dict[str, Any] = {
            "risk_metrics": metrics,
            # nav_to_returns 由 n 个净值产生 n-1 个收益，日期需同步去掉首日
            "monthly_returns": monthly_returns(dates[1:], rets),
            "risk_gate": evaluate_risk_gate(metrics, max_position_pct=exposure["max_position_pct"]),
            "exposure": exposure,
        }
        if include_monte_carlo:
            # 多策略对比场景用较少模拟次数（每条曲线都要算，控制响应时间）
            out["monte_carlo"] = monte_carlo_summary(rets, sims=400, block=20, seed=42)
        return out
    except Exception as e:  # 风控计算失败不应让回测结果消失
        logger.warning("风险指标计算失败: %r", e)
        return {}


# ---- 多策略对比 ----


class CompareRequest(BaseModel):
    strategy_ids: list[str] = Field(..., description="策略 id 列表，1-8 个")
    vt_symbol: str = Field("600519.SSE", description="vn.py 标的，如 600519.SSE")
    start: str = "2024-01-01"
    end: str | None = None


@router.post("/compare")
def compare_strategies(body: CompareRequest):
    return _compare_impl(body)


def _compare_impl(body: CompareRequest, progress=None, cancelled=None):
    """同一标的、同一区间跑多个策略，输出收益曲线 + 统计对比。"""
    ids = [str(s).zfill(2) for s in body.strategy_ids][:MAX_COMPARE]
    if not ids:
        raise HTTPException(status_code=400, detail="strategy_ids 不能为空")
    end = body.end or date.today().isoformat()
    cfg_base = {"vt_symbol": body.vt_symbol, "start": body.start, "end": end}

    pool = _executor()
    futures = {pool.submit(_run_backtest, sid, cfg_base): sid for sid in ids}
    results = []
    for fut in futures:
        if cancelled is not None and cancelled():
            raise JobCancelled()
        try:
            results.append(fut.result(timeout=300))
        except Exception as e:
            logger.exception("对比回测失败")
            results.append({"ok": False, "error": str(e)})
        if progress is not None:
            progress(1, "backtest")

    ok_results = [r for r in results if r.get("ok")]
    # 统一日期轴（取最长序列，其余按日期对齐）
    all_dates = sorted({d for r in ok_results for d in r["series"]["dates"]})
    aligned = {}
    date_index = {d: i for i, d in enumerate(all_dates)}
    for r in ok_results:
        s = r["series"]
        arr = [None] * len(all_dates)
        for d, v in zip(s["dates"], s["returns"]):
            if d in date_index:
                arr[date_index[d]] = v
        aligned[r["strategy_id"]] = arr

    # 风险指标汇总（供前端按夏普/回撤排序，而非只看收益）
    risk_summary = {
        r["strategy_id"]: {
            "class_name": r.get("class_name"),
            "sharpe": (r.get("risk_metrics") or {}).get("risk_metrics", {}).get("sharpe_ratio"),
            "sortino": (r.get("risk_metrics") or {}).get("risk_metrics", {}).get("sortino_ratio"),
            "max_drawdown_pct": (r.get("risk_metrics") or {}).get("risk_metrics", {}).get("max_drawdown_pct"),
            "var_95_pct": (r.get("risk_metrics") or {}).get("risk_metrics", {}).get("var_95_pct"),
            "risk_gate": (r.get("risk_metrics") or {}).get("risk_gate", {}).get("verdict"),
        }
        for r in ok_results
    }

    return {
        "success": len(ok_results) > 0,
        "vt_symbol": body.vt_symbol,
        "start": body.start,
        "end": end,
        "dates": all_dates,
        "curves": aligned,
        "results": results,
        "risk_summary": risk_summary,
        "message": f"成功 {len(ok_results)}/{len(ids)} 个策略" if ok_results else "全部策略回测失败，请确认已同步行情数据",
    }


# ---- 因子选股 ----


class ScreenRequest(BaseModel):
    universe_limit: int = Field(120, ge=10, le=400, description="参与打分的股票数量上限")
    top_n: int = Field(20, ge=5, le=100)
    lookback_days: int = Field(120, ge=40, le=400)
    end_date: str | None = None


def _load_daily_df(vt_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """按 免费源 → 本地 vn.py 库 顺序取日线，返回 TuShare 兼容列 DataFrame。"""
    from routers.free_market import vt_to_tx

    tx = vt_to_tx(vt_code)
    # 1) 免费腾讯接口
    for attempt in (0, 1):
        try:
            df = free_daily(tx, start_date, end_date)
            if df is not None and len(df) >= 30:
                return df
        except Exception:
            if attempt == 0:
                time.sleep(1.0)
            else:
                break
    # 2) 本地 vn.py 数据库兜底（免费源不可用/数据不足时）
    try:
        from vnpy.trader.constant import Exchange, Interval
        from vnpy.trader.database import get_database

        code, _, suf = vt_code.partition(".")
        suf = suf.upper()
        exchange = {"SSE": Exchange.SSE, "SZSE": Exchange.SZSE, "BSE": Exchange.BSE}.get(suf)
        if exchange is None:
            return pd.DataFrame()
        bars = get_database().load_bar_data(code, exchange, Interval.DAILY, start_date, end_date)
        if not bars:
            return pd.DataFrame()
        records = [
            {
                "ts_code": vt_code,
                "trade_date": bar.datetime.strftime("%Y%m%d"),
                "open": bar.open_price,
                "high": bar.high_price,
                "low": bar.low_price,
                "close": bar.close_price,
                "vol": float(bar.volume),
                "amount": 0.0,
            }
            for bar in bars
        ]
        df = pd.DataFrame(records)
        return df
    except Exception:
        return pd.DataFrame()


def _compute_factors(vt_code: str, lookback: int, end_date: str) -> dict | None:
    """抓单只日线，算多因子原始值。vt_code 形如 600519.SSE。返回 None 表示数据不足。"""
    from routers.free_market import vt_to_tx

    tx = vt_to_tx(vt_code)
    raw = vt_code

    end_d = pd.Timestamp(end_date) if end_date else pd.Timestamp.today().normalize()
    start_d = (end_d - pd.Timedelta(days=int(lookback * 2.2))).strftime("%Y-%m-%d")

    df = _load_daily_df(vt_code, start_d, end_d.strftime("%Y-%m-%d"))
    if df is None or len(df) < max(30, lookback // 2):
        return None

    df = df.sort_values("trade_date").reset_index(drop=True)
    close = df["close"].astype(float).to_numpy()
    high = df["high"].astype(float).to_numpy()
    low = df["low"].astype(float).to_numpy()
    vol = df.get("vol")
    vol = vol.astype(float).to_numpy() if vol is not None else np.zeros(len(df))

    n = min(lookback, len(close))
    c, h, l, v = close[-n:], high[-n:], low[-n:], vol[-n:]
    if len(c) < 30 or c[0] <= 0:
        return None

    # 各因子（原始值，后面统一做横截面 rank 打分）
    mom = c[-1] / c[0] - 1.0                                        # 动量（区间涨幅）
    ma20 = c[-20:].mean()
    ma60 = c[-60:].mean() if len(c) >= 60 else ma20
    ma_bias = c[-1] / ma20 - 1.0                                    # 短期偏离（均值回复为负向）
    trend = c[-1] / ma60 - 1.0                                      # 中期趋势
    rets = np.diff(c) / c[:-1]
    vola = float(np.std(rets[-60:]) * math.sqrt(252)) if len(rets) >= 20 else float(np.std(rets) * math.sqrt(252))
    v_ma = v[-20:].mean()
    vol_ratio = (v[-5:].mean() / v_ma) if v_ma > 0 else 1.0         # 量能放大
    amihud = float(np.mean(np.abs(rets[-20:]) / (v[-20:] + 1e-9))) if len(rets) >= 20 else 0.0  # 流动性/冲击
    hi60, lo60 = float(np.max(h[-60:])), float(np.min(l[-60:])) if len(c) >= 60 else (float(np.max(h)), float(np.min(l)))
    dd = c[-1] / hi60 - 1.0 if hi60 > 0 else 0.0                     # 距60日高点回撤
    ma_cross = float(1.0 if ma20 > ma60 else (-1.0 if ma20 < ma60 else 0.0))

    return {
        "ts_code": raw,
        "close": float(c[-1]),
        "mom": mom, "trend": trend, "ma_bias": ma_bias, "volatility": vola,
        "vol_ratio": vol_ratio, "amihud": amihud, "drawdown_from_high": dd, "ma_cross": float(ma_cross),
        "_n": len(c),
    }


@router.post("/screen")
def screen_stocks(body: ScreenRequest):
    """多因子打分选股：全市场取样 → 计算因子 → 横截面 rank 加权 → Top N。"""
    end_date = body.end_date or date.today().isoformat()
    try:
        stocks = free_list()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取股票列表失败: {e}") from e
    if stocks is None or stocks.empty:
        raise HTTPException(status_code=502, detail="股票列表为空")

    # 取样：从全市场均匀抽样，控制请求量
    pool = stocks.head(body.universe_limit * 3) if len(stocks) > body.universe_limit * 3 else stocks
    from routers.free_market import vt_to_tx

    vt_codes = []
    for _, r in pool.iterrows():
        code = str(r.get("ts_code", "")).upper()
        if not code or "." not in code:
            continue
        try:
            vt_codes.append((vt_to_tx(code), code, str(r.get("name", ""))))
        except Exception:
            continue
    vt_codes = vt_codes[: body.universe_limit]

    # 腾讯接口对并发连接限流（返回 HTTP 424），这里串行抓取并加小间隔
    rows = []
    for vt, code, name in vt_codes:
        try:
            f = _compute_factors(code, body.lookback_days, end_date)
        except Exception:
            f = None
        if f:
            f["name"] = name
            rows.append(f)
        time.sleep(0.05)

    if len(rows) < 5:
        return {"success": False, "items": [], "message": f"仅 {len(rows)} 只股票数据充足，无法打分（请稍后重试或减少 lookback）"}

    df = pd.DataFrame(rows)

    # 因子方向：越大越好 vs 越小越好
    positive = ["mom", "trend", "vol_ratio", "ma_cross"]
    negative = ["volatility", "amihud", "drawdown_from_high", "ma_bias"]
    weights = {
        "mom": 0.25, "trend": 0.20, "vol_ratio": 0.10, "ma_cross": 0.10,
        "volatility": 0.15, "amihud": 0.10, "drawdown_from_high": 0.10, "ma_bias": 0.10,
    }

    score = pd.Series(0.0, index=df.index)
    for col in positive + negative:
        pct = df[col].rank(pct=True)
        score = score + (pct if col in positive else (1 - pct)) * weights.get(col, 0.0)
    df["score"] = score * 100

    top = df.sort_values("score", ascending=False).head(body.top_n)
    items = []
    for _, r in top.iterrows():
        items.append({
            "ts_code": r["ts_code"],
            "vt_symbol": ts_code_to_vt_symbol(str(r["ts_code"])),
            "name": r["name"],
            "close": _safe(r["close"]),
            "score": round(float(r["score"]), 2),
            "factors": {
                "mom": round(float(r["mom"]) * 100, 2),
                "trend": round(float(r["trend"]) * 100, 2),
                "volatility": round(float(r["volatility"]) * 100, 2),
                "vol_ratio": round(float(r["vol_ratio"]), 2),
                "drawdown_from_high": round(float(r["drawdown_from_high"]) * 100, 2),
            },
        })

    return {
        "success": True,
        "universe": len(df),
        "scanned": len(vt_codes),
        "lookback_days": body.lookback_days,
        "items": items,
        "factors_used": list(weights.keys()),
        "message": f"从 {len(df)} 只数据充足标的中选出 Top {len(items)}",
    }


# ---- 参数网格优化 ----


class GridRequest(BaseModel):
    strategy_id: str
    param_name: str = Field("fast_window", description="要扫描的参数名（策略 parameters 之一）")
    values: list[float] = Field(..., description="参数取值列表，如 [5,10,15,20]")
    param2: str | None = Field(None, description="第二维参数名（双因子热力图时提供）")
    values2: list[float] | None = Field(None, description="第二维参数取值列表")
    fixed_params: dict[str, float] | None = Field(None, description="其他固定参数")
    vt_symbol: str = "600519.SSE"
    start: str = "2024-01-01"
    end: str | None = None
    capital: int = 10_000
    objective: str = Field(
        "sharpe",
        description="寻优目标：sharpe（风险调整后）/ total_return（纯收益，仅用于对比过拟合风险）",
    )
    apply_risk_gate: bool = Field(True, description="是否用确定性风控闸门过滤不合格参数组合")


@router.post("/grid")
def grid_optimize(body: GridRequest):
    return _grid_impl(body)


def _grid_impl(body: GridRequest, progress=None, cancelled=None):
    """参数网格扫描：单参数或多参数（双因子热力图）。

    寻优口径：
      - objective=sharpe（默认）：按风险调整后收益排序，**降低过拟合风险**
      - objective=total_return：按纯收益排序，仅用于观察参数曲面是否只有孤立尖峰
      - apply_risk_gate=True：先用确定性硬规则过滤不合格组合，剩余中再择优
    """
    values = [float(v) for v in body.values][:16]
    if len(values) < 2:
        raise HTTPException(status_code=400, detail="至少提供 2 个参数取值")

    if body.objective not in ("sharpe", "total_return"):
        raise HTTPException(status_code=400, detail="objective 仅支持 sharpe / total_return")

    sid = str(body.strategy_id).zfill(2)
    end = body.end or date.today().isoformat()
    cfg_base = {"vt_symbol": body.vt_symbol, "start": body.start, "end": end, "capital": body.capital}
    if body.fixed_params:
        cfg_base.update(body.fixed_params)

    param2 = body.param2
    values2 = [float(v) for v in body.values2][:16] if (param2 and body.values2) else []
    is_2d = bool(param2 and values2)
    if is_2d:
        cells_total = len(values) * len(values2)
        if cells_total > MAX_GRID_CELLS:
            raise HTTPException(status_code=400, detail=f"网格组合数 {cells_total} 超过上限 {MAX_GRID_CELLS}")

    cache_key = json.dumps(
        {"sid": sid, "p1": body.param_name, "v1": values, "p2": param2, "v2": values2, "c": cfg_base,
         "obj": body.objective, "gate": body.apply_risk_gate},
        sort_keys=True,
    )
    cached = _grid_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < 1800:
        return {**cached["data"], "cached": True}

    pool = _executor()

    def _submit(p1: float, p2: float | None):
        cfg = dict(cfg_base)
        cfg[body.param_name] = (int(p1) if p1.is_integer() else p1)
        if p2 is not None:
            cfg[param2] = (int(p2) if p2.is_integer() else p2)
        return pool.submit(_run_backtest, sid, cfg, False), p1, p2

    def _score(cell: dict) -> float | None:
        """按寻优目标取排序分。"""
        if not cell.get("ok"):
            return None
        if body.objective == "sharpe":
            s = cell.get("sharpe")
            return float(s) if isinstance(s, (int, float)) else None
        return cell.get("total_return")

    if is_2d:
        # 双因子：以 (v1, v2) 为键收集，方便组矩阵
        futures = []
        for v1 in values:
            for v2 in values2:
                futures.append(_submit(v1, v2))
        results_by_cell: dict[tuple[float, float], dict] = {}
        best_class = None
        for fut, v1, v2 in futures:
            if cancelled is not None and cancelled():
                raise JobCancelled()
            try:
                r = fut.result(timeout=300)
            except Exception as e:
                r = {"ok": False, "error": str(e)}
            if progress is not None:
                progress(1, f"{body.param_name}={v1} {param2}={v2}")
            if r.get("ok"):
                best_class = r.get("class_name") or best_class
                st = r.get("stats", {})
                rm = r.get("risk_metrics") or {}
                gate = (r.get("risk_metrics") or {}).get("risk_gate") or {}
                gate_ok = (not body.apply_risk_gate) or bool(gate.get("approved", True))
                tr = st.get("total_return")
                results_by_cell[(v1, v2)] = {
                    "ok": True,
                    "gate_ok": gate_ok,
                    "gate_reasons": gate.get("reasons", []),
                    "total_return": round(float(tr), 3) if isinstance(tr, (int, float)) else None,
                    "max_drawdown": round(float(st.get("max_drawdown", 0) or 0), 3) if isinstance(st.get("max_drawdown"), (int, float)) else None,
                    "sharpe": _safe(st.get("sharpe_ratio")),
                    "sortino": rm.get("risk_metrics", {}).get("sortino_ratio") if rm else None,
                    "calmar": rm.get("risk_metrics", {}).get("calmar_ratio") if rm else None,
                    "var_95_pct": rm.get("risk_metrics", {}).get("var_95_pct") if rm else None,
                    "trade_count": r.get("trade_count", 0),
                }
            else:
                results_by_cell[(v1, v2)] = {"ok": False, "error": r.get("error", "回测失败")}

        # 热力图矩阵
        matrix = []
        best = None
        rejected = 0
        for v1 in values:
            row = []
            for v2 in values2:
                cell = results_by_cell.get((v1, v2), {"ok": False, "error": "?"})
                row.append(cell.get("total_return") if cell.get("ok") else None)
                if cell.get("ok") and not cell.get("gate_ok", True):
                    rejected += 1
                elif cell.get("ok") and cell.get("total_return") is not None:
                    score = _score(cell)
                    if score is not None and (best is None or score > best["_score"]):
                        best = {"p1": v1, "p2": v2, "total_return": cell["total_return"], "_score": score,
                                **{k: cell[k] for k in ("max_drawdown", "sharpe", "sortino", "calmar", "var_95_pct", "trade_count")}}
            matrix.append(row)

        if best is not None:
            best.pop("_score", None)

        data = {
            "success": best is not None,
            "strategy_id": sid,
            "class_name": best_class,
            "param_name": body.param_name,
            "param2": param2,
            "values": values,
            "values2": values2,
            "matrix": matrix,
            "best": best,
            "objective": body.objective,
            "risk_gate_applied": body.apply_risk_gate,
            "risk_gate_rejected": rejected,
            "vt_symbol": body.vt_symbol,
            "start": body.start,
            "end": end,
            "cells": len(results_by_cell),
            "mode": "2d",
            "message": (
                f"扫描 {len(values)}×{len(values2)} 组参数"
                + (f"，按 {body.objective} 择优：{body.param_name}={best['p1']} & {param2}={best['p2']}"
                   f"（收益 {best['total_return']}%，夏普 {best.get('sharpe')}）" if best else "（无有效结果）")
                + (f"，风控闸门过滤 {rejected} 组" if body.apply_risk_gate and rejected else "")
            ),
        }
        _grid_cache[cache_key] = {"ts": time.time(), "data": data}
        return data

    # ---- 单参数模式（原逻辑） ----
    futures = {}
    for v in values:
        cfg = dict(cfg_base)
        cfg[body.param_name] = (int(v) if v.is_integer() else v)
        futures[pool.submit(_run_backtest, sid, cfg, False)] = v

    cells = []
    best_class = None
    best = None
    rejected = 0
    for fut, v in futures.items():
        if cancelled is not None and cancelled():
            raise JobCancelled()
        try:
            r = fut.result(timeout=300)
        except Exception as e:
            r = {"ok": False, "error": str(e)}
        if progress is not None:
            progress(1, f"{body.param_name}={v}")
        if r.get("ok"):
            st = r.get("stats", {})
            best_class = r.get("class_name")
            total_return = st.get("total_return")
            dd = st.get("max_drawdown")
            rm = (r.get("risk_metrics") or {}).get("risk_metrics") or {}
            gate = (r.get("risk_metrics") or {}).get("risk_gate") or {}
            gate_ok = (not body.apply_risk_gate) or bool(gate.get("approved", True))
            if not gate_ok:
                rejected += 1
            cell = {
                "value": v,
                "ok": True,
                "gate_ok": gate_ok,
                "gate_reasons": gate.get("reasons", []),
                "total_return": round(float(total_return), 3) if isinstance(total_return, (int, float)) else None,
                "annual_return": _safe(st.get("annual_return")),
                "max_drawdown": round(float(dd), 3) if isinstance(dd, (int, float)) else None,
                "sharpe": _safe(st.get("sharpe_ratio")),
                "sortino": rm.get("sortino_ratio"),
                "calmar": rm.get("calmar_ratio"),
                "var_95_pct": rm.get("var_95_pct"),
                "cvar_95_pct": rm.get("cvar_95_pct"),
                "trade_count": r.get("trade_count", 0),
            }
            cells.append(cell)
            score = _score(cell)
            if score is not None and cell["gate_ok"] and (best is None or score > best["_score"]):
                best = {**cell, "_score": score}
        else:
            cells.append({"value": v, "ok": False, "error": r.get("error", "回测失败")})

    if best is not None:
        best.pop("_score", None)

    data = {
        "success": any(c["ok"] for c in cells),
        "strategy_id": sid,
        "class_name": best_class,
        "param_name": body.param_name,
        "vt_symbol": body.vt_symbol,
        "start": body.start,
        "end": end,
        "cells": sorted(cells, key=lambda c: c["value"]),
        "best": best,
        "objective": body.objective,
        "risk_gate_applied": body.apply_risk_gate,
        "risk_gate_rejected": rejected,
        "mode": "1d",
        "message": (
            f"扫描 {len(cells)} 组参数"
            + (f"，按 {body.objective} 择优 {body.param_name}={best['value']}"
               f"（收益 {best['total_return']}%，夏普 {best.get('sharpe')}）" if best else "（无通过风控的有效结果）")
            + (f"，风控闸门过滤 {rejected} 组" if body.apply_risk_gate and rejected else "")
        ),
    }
    _grid_cache[cache_key] = {"ts": time.time(), "data": data}
    return data


# ---- 实时行情 WebSocket ----

_watch_subs: set[str] = set()


class WatchRequest(BaseModel):
    symbols: list[str] = Field(..., description="腾讯代码，如 sh600519")


@router.get("/realtime")
def realtime_quotes(symbols: str = Query("sh600519", description="逗号分隔的腾讯代码")):
    """拉取实时快照（REST，供 WS 不可用时降级）。"""
    from routers.free_market import _fetch_quotes

    codes = [s.strip() for s in symbols.split(",") if s.strip()][:60]
    if not codes:
        raise HTTPException(status_code=400, detail="symbols 不能为空")
    try:
        df = _fetch_quotes(codes)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"实时行情获取失败: {e}") from e
    if df is None or df.empty:
        return {"items": [], "message": "无数据"}
    records = df.to_dict(orient="records")
    return {"items": records, "count": len(records)}


@router.websocket("/ws")
async def realtime_ws(websocket: WebSocket):
    """WebSocket 实时推送：客户端连上后每 3 秒推送一次快照。"""
    await websocket.accept()
    logger.info("WS connected")
    try:
        symbols: list[str] = []
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=3.0)
                if isinstance(msg, dict) and "symbols" in msg:
                    symbols = [str(s).strip() for s in msg["symbols"] if str(s).strip()][:60]
                    logger.info("WS subscribed: %s", symbols[:5])
            except asyncio.TimeoutError:
                pass

            if symbols:
                try:
                    payload = await asyncio.get_running_loop().run_in_executor(
                        _executor(), lambda: _snapshot(symbols)
                    )
                except Exception as e:
                    logger.exception("WS snapshot error")
                    payload = {"items": [], "error": str(e)}
                await websocket.send_json(payload)
            else:
                await websocket.send_json({"items": [], "message": "等待订阅 symbols"})
            await asyncio.sleep(3)
    except Exception as e:
        logger.warning("WS closed: %r", e)
        try:
            await websocket.close()
        except Exception:
            pass


def _snapshot(symbols: list[str]) -> dict:
    from routers.free_market import _fetch_quotes

    try:
        df = _fetch_quotes(symbols)
    except Exception as e:
        return {"items": [], "error": str(e)}
    if df is None or df.empty:
        return {"items": [], "message": "无数据"}
    return {"items": df.to_dict(orient="records"), "count": len(df), "ts": int(time.time() * 1000)}


# ---- 组合回测（Portfolio） ----


class PortfolioRequest(BaseModel):
    strategy_id: str = Field(..., description="策略 id")
    vt_symbols: list[str] = Field(..., description="组合标的列表，2-10 个")
    weights: list[float] | None = Field(None, description="等权重时可省略")
    start: str = "2024-01-01"
    end: str | None = None
    capital: int = 100_000
    rate: float = 0.0003
    slippage: float = 0.01
    pricetick: float = 0.01
    size: float = 1
    fixed_params: dict[str, float] | None = None
    notional_per_symbol: list[float] | None = Field(
        None,
        description=(
            "每个标的的目标名义金额（元），长度需与 vt_symbols 一致。"
            "不传时退化为 fixed_params.fixed_size 的股数模式。"
            "组合等权必须用名义金额而非股数——一篮子标的价格从 7 元到 2300 元，"
            "固定股数会让实际权重严重偏离设定权重。"
        ),
    )


def _fetch_first_close(cfg: dict) -> float | None:
    """只取某标的在回测区间内的第一根日线收盘价，用于名义金额换算股数。

    不走完整回测：直接读本地库的第一根 bar，比跑一次回测便宜两个数量级。
    """
    from vnpy.trader.constant import Interval
    from vnpy.trader.database import get_database
    from examples.cta_backtesting.run_rewritten_strategy_backtest import parse_date

    try:
        vt = cfg["vt_symbol"]
        db = get_database()
        ov = [b for b in db.get_bar_overview() if f"{b.symbol}.{b.exchange.value}" == vt]
        if not ov:
            return None
        b = ov[0]
        bars = db.load_bar_data(
            b.symbol,
            b.exchange,
            Interval.DAILY,
            parse_date(cfg["start"]),
            parse_date(cfg["end"]),
        )
        if not bars:
            return None
        px = float(bars[0].close_price)
        return px if px > 0 else None
    except Exception as e:
        logger.warning("first_close 获取失败 %s: %s", cfg.get("vt_symbol"), e)
        return None


def shares_for_notional(
    symbols: list[str], notionals: list[float], prices: list[float | None]
) -> dict[str, float]:
    """按目标名义金额与期初价换算股数；价格或金额无效的标的直接跳过。

    为什么不用固定股数：一篮子标的价格可能相差数百倍，同样的股数会让实际
    名义金额（进而权重）严重偏离设定值。
    """
    out: dict[str, float] = {}
    for sym, target, px in zip(symbols, notionals, prices):
        if not px or px <= 0:
            continue
        t = float(target)
        if t <= 0:
            continue
        out[sym] = max(1.0, round(t / px))
    return out


def combine_sleeve_returns(
    date_rets: dict[str, dict[str, float]],
    weights: dict[str, float],
    use_sum: bool,
) -> tuple[list[str], list[float]]:
    """合成各标的 sleeve 日收益为组合日收益。

    use_sum=True（名义金额模式）：资金分配已体现在各 sleeve 仓位里，直接求和。
    再乘一次权重会让权重被平方。
    use_sum=False（固定股数模式，历史行为）：按权重加权求和。
    """
    all_dates = sorted({d for srets in date_rets.values() for d in srets})
    out: list[float] = []
    for d in all_dates:
        if use_sum:
            out.append(sum(srets.get(d, 0.0) for srets in date_rets.values()))
        else:
            out.append(sum(float(weights.get(s, 0.0)) * srets.get(d, 0.0) for s, srets in date_rets.items()))
    return all_dates, out


@router.post("/portfolio")
def portfolio_backtest(body: PortfolioRequest):
    return _portfolio_impl(body)


def _portfolio_impl(body: PortfolioRequest, progress=None, cancelled=None):
    """组合回测：同一策略在多标的上分别出信号，按目标名义金额分配仓位。

    说明：项目策略族基于 vn.py CtaTemplate，这里做组合回测采用「信号照搬」方案——
    每个标的独立运行该策略，用目标仓位驱动组合引擎，得到组合净值/回撤。
    """
    import sys as _sys

    symbols = [str(s) for s in body.vt_symbols if str(s).strip()]
    if len(symbols) < 2:
        raise HTTPException(status_code=400, detail="组合至少需要 2 个标的")
    if len(symbols) > 10:
        symbols = symbols[:10]  # 上限 10 个，超过的部分截断而非报错

    # weights / notional_per_symbol 都必须与截断后的 symbols 对齐
    weights = body.weights[:len(symbols)] if body.weights else None
    notional = body.notional_per_symbol[:len(symbols)] if body.notional_per_symbol else None
    if weights is not None and len(weights) != len(symbols):
        raise HTTPException(status_code=400, detail="weights 长度必须与 vt_symbols 一致")
    if notional is not None and len(notional) != len(symbols):
        raise HTTPException(status_code=400, detail="notional_per_symbol 长度必须与 vt_symbols 一致")
    if weights is None:
        weights = [1.0 / len(symbols)] * len(symbols)
    total_w = sum(float(w) for w in weights)
    if total_w <= 0:
        raise HTTPException(status_code=400, detail="权重之和必须为正")
    weights = [float(w) / total_w for w in weights]  # 归一化

    sid = str(body.strategy_id).zfill(2)
    end = body.end or date.today().isoformat()

    # 每个标的跑一次单策略回测，取 balance 序列 → 等权/加权拼组合净值
    from datetime import datetime

    from examples.cta_backtesting.run_rewritten_strategy_backtest import parse_date

    script_dir = Path(__file__).resolve().parent.parent / "examples" / "cta_backtesting"
    if str(script_dir) not in _sys.path:
        _sys.path.insert(0, str(script_dir))

    pool = _executor()
    cfg_base = {
        "vt_symbol": None,
        "start": body.start,
        "end": end,
        "rate": body.rate,
        "slippage": body.slippage,
        "size": body.size,
        "pricetick": body.pricetick,
        "capital": body.capital,
    }
    if body.fixed_params:
        cfg_base.update(body.fixed_params)

    if notional is not None and len(notional) != len(symbols):
        raise HTTPException(status_code=400, detail="notional_per_symbol 长度必须与 vt_symbols 一致")

    # 名义金额模式：先取各标的期初价换算股数（只读第一根 bar，不跑回测）
    prices: list[float | None] = []
    fixed_size_by_symbol: dict[str, float] = {}
    first_close_by_symbol: dict[str, float] = {}
    if notional is not None:
        for sym in symbols:
            prices.append(_fetch_first_close({**cfg_base, "vt_symbol": sym}))
        fixed_size_by_symbol = shares_for_notional(symbols, notional, prices)
        first_close_by_symbol = {
            sym: px for sym, px in zip(symbols, prices) if px and px > 0 and sym in fixed_size_by_symbol
        }

    futures = {}
    for sym in symbols:
        cfg = {**cfg_base, "vt_symbol": sym}
        if sym in fixed_size_by_symbol:
            cfg["fixed_size"] = fixed_size_by_symbol[sym]
        futures[pool.submit(_run_backtest, sid, cfg, False)] = sym

    # 收集每个标的的日收益序列，按日期对齐后加权合成组合净值
    date_rets: dict[str, dict[str, float]] = {}
    symbol_class = None
    per_symbol = []
    for fut, s in futures.items():
        if cancelled is not None and cancelled():
            raise JobCancelled()
        try:
            r = fut.result(timeout=300)
        except Exception as e:
            r = {"ok": False, "error": str(e)}
        if progress is not None:
            progress(1, f"sleeve {s}")
        if not r.get("ok"):
            per_symbol.append({"vt_symbol": s, "ok": False, "error": r.get("error", "回测失败")})
            continue
        symbol_class = r.get("class_name")
        series = r["series"]
        rets = series.get("returns") or []
        if not rets or len(rets) != len(series["dates"]):
            per_symbol.append({"vt_symbol": s, "ok": False, "error": "无成交记录，无法生成组合收益"})
            continue
        # returns 是区间累计收益%（起点 0），转日收益序列
        srets: dict[str, float] = {}
        prev = None
        for d, cum in zip(series["dates"], rets):
            if cum is None:
                continue
            if prev is None:
                srets[d] = 0.0
            else:
                srets[d] = (cum / 100.0 + 1.0) / (prev / 100.0 + 1.0) - 1.0
            prev = cum
        date_rets[s] = srets
        _px = r.get("first_close") or first_close_by_symbol.get(s)
        _fs = fixed_size_by_symbol.get(s)
        per_symbol.append(
            {
                "vt_symbol": s,
                "ok": True,
                "class_name": r.get("class_name"),
                "total_return": round(float(r["stats"].get("total_return", 0) or 0), 3),
                "trade_count": r.get("trade_count", 0),
                "first_close": _px,
                "fixed_size": _fs,
                "target_notional": (round(_px * _fs, 2) if (_px and _fs) else None),
            }
        )

    if not date_rets:
        dropped_all = [s for s in symbols if s not in date_rets]
        return {
            "success": False,
            "strategy_id": sid,
            "message": "组合中所有标的回测失败，请确认已同步行情数据",
            "per_symbol": per_symbol,
            "dropped_symbols": dropped_all,
        }

    use_sum = notional is not None
    all_dates, comb_list = combine_sleeve_returns(
        date_rets,
        {s: float(weights[symbols.index(s)]) for s in date_rets},
        use_sum=use_sum,
    )
    comb_ret = dict(zip(all_dates, comb_list))

    # 组合绩效统一走 risk_metrics 口径（与单策略回测一致，便于横向比较）
    port_returns = comb_list
    metrics = compute_risk_metrics(port_returns)

    nav = 1.0
    navs: list[float] = []
    for r in port_returns:
        nav *= 1.0 + r
        navs.append(round(nav, 6))

    total_ret = navs[-1] - 1.0 if navs else 0.0

    # 各标的权重展示：只统计真正进入组合的 sleeve（回测失败的标的不计入分母，
    # 否则权重之和为 1 但实际少了一腿，组合收益会被高估）。
    dropped = [s for s in symbols if s not in date_rets]
    active = [s for s in symbols if s in date_rets]
    if use_sum:
        _notionals = [
            (first_close_by_symbol[s] * fixed_size_by_symbol[s]) if s in fixed_size_by_symbol else 0.0
            for s in active
        ]
        _sum_n = sum(_notionals) or 1.0
        weight_info = [
            {
                "vt_symbol": s,
                "weight": round(n / _sum_n, 4),
                "target_notional": round(n, 2) if n > 0 else None,
                "fixed_size": fixed_size_by_symbol.get(s),
                "first_close": first_close_by_symbol.get(s),
            }
            for s, n in zip(active, _notionals)
        ]
    else:
        weight_info = [
            {"vt_symbol": s, "weight": round(float(weights[symbols.index(s)]), 4)}
            for s in active
        ]

    return {
        "success": True,
        "strategy_id": sid,
        "class_name": symbol_class,
        "vt_symbols": symbols,
        "weights": weight_info,
        "start": body.start,
        "end": end,
        "dates": all_dates,
        "nav": navs,
        "stats": {
            "total_return": metrics["total_return_pct"],
            "annual_return": metrics["annual_return_pct"],
            "annual_volatility_pct": metrics["annual_volatility_pct"],
            "max_drawdown": round(-metrics["max_drawdown_pct"], 3),
            "sharpe_ratio": metrics["sharpe_ratio"],
            "sortino_ratio": metrics["sortino_ratio"],
            "calmar_ratio": metrics["calmar_ratio"],
            "var_95_pct": metrics["var_95_pct"],
            "total_trade_count": sum(p.get("trade_count", 0) for p in per_symbol if p.get("ok")),
        },
        "risk_metrics": metrics,
        "monthly_returns": monthly_returns(all_dates, port_returns),
        "per_symbol": per_symbol,
        "caveat": (
            "「信号照搬」式组合回测：每个标的独立运行同一策略，按各自目标名义金额定仓后"
            "合成日收益。未建模标的间相关性、共享资金池、再平衡成本与同时开仓的资金占用，"
            "不等于真实组合绩效。" if use_sum else
            "「信号照搬」式组合回测：每个标的独立分得一份资金后等权/加权合成，"
            "未建模标的间相关性、共享资金池、再平衡成本与同时开仓的资金占用，"
            "不等于真实组合绩效。注意固定股数模式下不同标的名义金额不一致，"
            "实际权重会偏离 weights；建议改用 notional_per_symbol 按名义金额分配。"
        ),
        "size_mode": "notional" if use_sum else "fixed_shares",
        "message": f"组合回测完成：{len(date_rets)}/{len(symbols)} 个标的有数据，加权净值 {round(total_ret * 100, 2)}%",
    }


# ---- 纸面交易（策略持仓模拟） ----


class PaperRequest(BaseModel):
    strategy_id: str = Field(..., description="策略 id")
    vt_symbol: str = Field("600519.SSE", description="标的")
    lookback: int = Field(120, ge=30, le=400, description="模拟回看天数")
    capital: int = Field(50_000, ge=10_000, le=5_000_000)
    fixed_params: dict[str, float] | None = None


@router.post("/paper")
def paper_trade(body: PaperRequest):
    """纸面交易：用**真实回测成交记录**推导当前持仓状态。

    流程：
      1. 确认该标的日线已在 vn.py 本地库（缺失则自动从免费源同步）
      2. 在最近 lookback 天窗口内运行真实策略回测
      3. 遍历成交记录，找出最后一笔未平仓交易 → 当前持仓方向 / 进场成本 / 浮动盈亏
      4. 信号历史取自真实成交（开仓=买入信号，平仓=卖出信号）
    """
    import sys as _sys

    script_dir = Path(__file__).resolve().parent.parent / "examples" / "cta_backtesting"
    if str(script_dir) not in _sys.path:
        _sys.path.insert(0, str(script_dir))

    sid = str(body.strategy_id).zfill(2)
    try:
        strategy_cls, row = load_strategy_class(sid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略加载失败: {e}") from e

    end_d = pd.Timestamp.today().normalize()
    start_d = (end_d - pd.Timedelta(days=int(body.lookback * 2.0))).strftime("%Y-%m-%d")

    # 1) 确保本地库有数据：优先免费源，拿到就写入 vn.py 数据库
    end_str = end_d.strftime("%Y-%m-%d")
    df = _load_daily_df(body.vt_symbol, start_d, end_str)
    if df is None or len(df) < 40:
        raise HTTPException(status_code=404, detail="免费源/本地库均无该标的足够日线，请稍后重试或更换标的")
    try:
        from routers.tushare_bars import bars_from_tushare_daily_df, save_bars_to_database

        save_bars_to_database(bars_from_tushare_daily_df(df.sort_values("trade_date")))
    except Exception:
        pass  # 写入失败不阻断（可能已存在）

    # 2) 真实回测
    overrides = dict(body.fixed_params or {})
    setting = build_setting(strategy_cls, row, overrides)
    cfg = {
        "strategy_id": sid,
        "vt_symbol": body.vt_symbol,
        "start": start_d,
        "end": end_str,
        "capital": body.capital,
    }
    cfg.update(overrides)

    try:
        stats, result_df, trades = _run_backtest_main(cfg)
    except Exception as e:
        logger.exception("纸面交易回测失败")
        raise HTTPException(status_code=500, detail=f"回测执行失败: {e}") from e

    trade_list = list(trades.values()) if isinstance(trades, dict) else list(trades or [])
    if not trade_list:
        raise HTTPException(
            status_code=404,
            detail="该策略在最近区间没有触发任何交易（成交笔数为 0），无法推导持仓。请调整参数或更换标的/区间。",
        )

    # 3) 遍历成交，推导当前持仓
    from vnpy.trader.constant import Direction, Offset

    position = 0  # 1 多 / -1 空 / 0 空仓
    entry_dt = None
    entry_price = None
    signals: list[dict] = []
    closed_rounds: list[dict] = []

    for t in trade_list:
        dt = getattr(t, "datetime", None)
        direction = getattr(t, "direction", None)
        offset = getattr(t, "offset", None)
        price = float(getattr(t, "price", 0) or 0)
        volume = float(getattr(t, "volume", 0) or 0)
        if not dt or direction is None or offset is None:
            continue
        is_open = offset == Offset.OPEN
        is_long = direction == Direction.LONG
        d_str = dt.strftime("%Y-%m-%d")

        if is_open:
            position = 1 if is_long else -1
            entry_dt = d_str
            entry_price = price
            signals.append({
                "date": d_str,
                "price": round(price, 3),
                "side": "buy" if is_long else "short",
                "position_after": position,
                "volume": volume,
                "is_open": True,
            })
        else:
            if position != 0 and entry_price:
                pnl_pct = ((price - entry_price) / entry_price * 100) if position > 0 else ((entry_price - price) / entry_price * 100)
                closed_rounds.append({
                    "side": "long" if position > 0 else "short",
                    "entry_date": entry_dt,
                    "entry_price": entry_price,
                    "exit_date": d_str,
                    "exit_price": price,
                    "return_pct": round(pnl_pct, 3),
                })
            signals.append({
                "date": d_str,
                "price": round(price, 3),
                "side": "sell" if is_long else "cover",
                "position_after": 0,
                "volume": volume,
                "is_open": False,
            })
            position = 0
            entry_dt = None
            entry_price = None

    # 4) 最新价与浮动盈亏
    close = df.sort_values("trade_date")["close"].astype(float)
    latest_price = float(close.iloc[-1]) if len(close) else 0.0
    unrealized = 0.0
    if position != 0 and entry_price:
        unrealized = ((latest_price - entry_price) / entry_price * 100) if position > 0 else ((entry_price - latest_price) / entry_price * 100)

    # 真实权益曲线
    nav: list[float] = []
    nav_dates: list[str] = []
    if result_df is not None and not result_df.empty and "balance" in result_df.columns:
        base = float(result_df["balance"].iloc[0]) or 1.0
        for idx, val in result_df["balance"].items():
            nav.append(round(float(val) / base, 6))
            nav_dates.append(idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx))

    win_rounds = [r for r in closed_rounds if r["return_pct"] > 0]
    pos_text = {1: "多", -1: "空", 0: "空仓"}.get(position)
    if closed_rounds:
        round_desc = (
            f"区间 {len(closed_rounds)} 个完整回合（胜率 {round(len(win_rounds) / len(closed_rounds) * 100, 1)}%）"
        )
    else:
        round_desc = "区间内尚未出现完整平仓回合"

    return {
        "success": True,
        "strategy_id": sid,
        "class_name": row["class_name"],
        "archetype": row["archetype"],
        "vt_symbol": body.vt_symbol,
        "position": pos_text,
        "position_code": position,
        "entry_date": entry_dt,
        "entry_price": entry_price,
        "latest_price": latest_price,
        "unrealized_pct": round(unrealized, 3),
        "signal_count": len(signals),
        "signals": signals[-12:],
        "closed_rounds": closed_rounds[-12:],
        "round_count": len(closed_rounds),
        "win_rate": (len(win_rounds) / len(closed_rounds) * 100) if closed_rounds else None,
        "params_used": {k: v for k, v in setting.items() if isinstance(v, (int, float))},
        "dates": nav_dates,
        "nav": nav,
        "capital": body.capital,
        "message": (
            f"当前{pos_text} · 浮动 {round(unrealized, 2)}% · {round_desc}"
        ),
    }


# ---- 全市场涨跌热力图 ----


class HeatmapRequest(BaseModel):
    sample: int = Field(900, ge=100, le=1500, description="取样股票数量（请求批次数）")
    end_date: str | None = None


@router.post("/heatmap")
def market_heatmap(body: HeatmapRequest):
    """全市场涨跌热力图：批量拉取实时快照，按涨跌幅分桶 + 尾部聚合。

    腾讯实时接口无稳定行业字段，这里按"涨跌幅格子"输出，颜色编码涨跌，
    直观展示市场广度（上涨家数/下跌家数/平盘）。
    """
    from routers.free_market import _fetch_quotes

    try:
        stocks = free_list()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取股票列表失败: {e}") from e
    if stocks is None or stocks.empty:
        raise HTTPException(status_code=502, detail="股票列表为空")

    # 取样：全市场均匀取前 N 只（免费接口一次性批量拉，控制请求量）
    df = stocks.head(body.sample)
    tx_codes = []
    from routers.free_market import vt_to_tx

    for _, r in df.iterrows():
        code = str(r.get("ts_code", "")).upper()
        if "." in code:
            try:
                tx_codes.append(vt_to_tx(code))
            except Exception:
                continue

    try:
        quotes = _fetch_quotes(tx_codes, batch=300)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"实时快照获取失败: {e}") from e
    if quotes is None or quotes.empty:
        raise HTTPException(status_code=502, detail="无实时快照")

    # 分桶：<=-7, -7~-4, -4~-2, -2~0, 0, 0~2, 2~4, 4~7, >=7
    buckets = [
        {"label": "≤-7%", "min": -999, "max": -7, "count": 0},
        {"label": "-7~-4%", "min": -7, "max": -4, "count": 0},
        {"label": "-4~-2%", "min": -4, "max": -2, "count": 0},
        {"label": "-2~0%", "min": -2, "max": 0, "count": 0},
        {"label": "0%", "min": 0, "max": 0, "count": 0},
        {"label": "0~2%", "min": 0, "max": 2, "count": 0},
        {"label": "2~4%", "min": 2, "max": 4, "count": 0},
        {"label": "4~7%", "min": 4, "max": 7, "count": 0},
        {"label": "≥7%", "min": 7, "max": 999, "count": 0},
    ]

    items = []
    up = down = flat = 0
    for _, row in quotes.iterrows():
        pct = float(row.get("change_pct", 0) or 0)
        code = str(row.get("ts_code", ""))
        name = str(row.get("name", ""))
        items.append({"ts_code": code, "name": name, "pct": round(pct, 2), "now": float(row.get("now", 0) or 0)})
        if pct > 0:
            up += 1
        elif pct < 0:
            down += 1
        else:
            flat += 1
        for b in buckets:
            if b["min"] <= pct < b["max"] if b["max"] != 0 else b["min"] <= pct <= b["max"]:
                b["count"] += 1
                break

    return {
        "success": True,
        "sample": len(items),
        "items": items,
        "buckets": buckets,
        "breadth": {"up": up, "down": down, "flat": flat},
        "message": f"取样 {len(items)} 只：上涨 {up} · 下跌 {down} · 平盘 {flat}",
    }