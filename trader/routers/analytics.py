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
)
from routers.free_market import fetch_daily as free_daily
from routers.free_market import fetch_stock_list as free_list
from routers.market_data import ts_code_to_vt_symbol

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_COMPARE = 8
MAX_GRID_CELLS = 60
_grid_cache: dict[str, Any] = {}
_executor_pool: ThreadPoolExecutor | None = None


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


def _run_backtest(sid: str, cfg: dict) -> dict:
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
    overrides = {k: cfg.get(k) for k in ("fast_window", "slow_window", "signal_window", "atr_window", "atr_mult", "fixed_size")}
    setting = build_setting(strategy_cls, row, overrides)
    engine.add_strategy(strategy_cls, setting)
    engine.load_data()
    if not engine.history_data:
        return {"ok": False, "strategy_id": sid, "class_name": row["class_name"], "error": "本地库无该标的日线数据，请先同步"}

    engine.run_backtesting()
    result_df = engine.calculate_result()
    stats = engine.calculate_statistics()

    series = {"dates": [], "balance": []}
    if result_df is not None and not result_df.empty:
        series["dates"] = [i.strftime("%Y-%m-%d") if hasattr(i, "strftime") else str(i) for i in result_df.index]
        if "balance" in result_df.columns:
            series["balance"] = [float(v) for v in result_df["balance"].fillna(0).tolist()]

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
    }


# ---- 多策略对比 ----


class CompareRequest(BaseModel):
    strategy_ids: list[str] = Field(..., description="策略 id 列表，1-8 个")
    vt_symbol: str = Field("600519.SSE", description="vn.py 标的，如 600519.SSE")
    start: str = "2024-01-01"
    end: str | None = None


@router.post("/compare")
def compare_strategies(body: CompareRequest):
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
        try:
            results.append(fut.result(timeout=300))
        except Exception as e:
            logger.exception("对比回测失败")
            results.append({"ok": False, "error": str(e)})

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

    return {
        "success": len(ok_results) > 0,
        "vt_symbol": body.vt_symbol,
        "start": body.start,
        "end": end,
        "dates": all_dates,
        "curves": aligned,
        "results": results,
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


@router.post("/grid")
def grid_optimize(body: GridRequest):
    """参数网格扫描：单参数或多参数（双因子热力图）。"""
    values = [float(v) for v in body.values][:16]
    if len(values) < 2:
        raise HTTPException(status_code=400, detail="至少提供 2 个参数取值")

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
        {"sid": sid, "p1": body.param_name, "v1": values, "p2": param2, "v2": values2, "c": cfg_base},
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
        return pool.submit(_run_backtest, sid, cfg), p1, p2

    if is_2d:
        # 双因子：以 (v1, v2) 为键收集，方便组矩阵
        futures = []
        for v1 in values:
            for v2 in values2:
                futures.append(_submit(v1, v2))
        results_by_cell: dict[tuple[float, float], dict] = {}
        best_class = None
        for fut, v1, v2 in futures:
            try:
                r = fut.result(timeout=300)
            except Exception as e:
                r = {"ok": False, "error": str(e)}
            if r.get("ok"):
                best_class = r.get("class_name") or best_class
                st = r.get("stats", {})
                tr = st.get("total_return")
                results_by_cell[(v1, v2)] = {
                    "ok": True,
                    "total_return": round(float(tr), 3) if isinstance(tr, (int, float)) else None,
                    "max_drawdown": round(float(st.get("max_drawdown", 0) or 0), 3) if isinstance(st.get("max_drawdown"), (int, float)) else None,
                    "sharpe": _safe(st.get("sharpe_ratio")),
                    "trade_count": r.get("trade_count", 0),
                }
            else:
                results_by_cell[(v1, v2)] = {"ok": False, "error": r.get("error", "回测失败")}

        # 热力图矩阵
        matrix = []
        best = None
        for v1 in values:
            row = []
            for v2 in values2:
                cell = results_by_cell.get((v1, v2), {"ok": False, "error": "?"})
                row.append(cell.get("total_return") if cell.get("ok") else None)
                if cell.get("ok") and cell.get("total_return") is not None:
                    if best is None or cell["total_return"] > best["total_return"]:
                        best = {"p1": v1, "p2": v2, "total_return": cell["total_return"], **{k: cell[k] for k in ("max_drawdown", "sharpe", "trade_count")}}
            matrix.append(row)

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
            "vt_symbol": body.vt_symbol,
            "start": body.start,
            "end": end,
            "cells": len(results_by_cell),
            "mode": "2d",
            "message": f"扫描 {len(values)}×{len(values2)} 组参数" + (f"，最佳 {body.param_name}={best['p1']} & {param2}={best['p2']}（总收益 {best['total_return']}%）" if best else "（无有效结果）"),
        }
        _grid_cache[cache_key] = {"ts": time.time(), "data": data}
        return data

    # ---- 单参数模式（原逻辑） ----
    futures = {}
    for v in values:
        cfg = dict(cfg_base)
        cfg[body.param_name] = (int(v) if v.is_integer() else v)
        futures[pool.submit(_run_backtest, sid, cfg)] = v

    cells = []
    best_class = None
    for fut, v in futures.items():
        try:
            r = fut.result(timeout=300)
        except Exception as e:
            r = {"ok": False, "error": str(e)}
        if r.get("ok"):
            st = r.get("stats", {})
            best_class = r.get("class_name")
            total_return = st.get("total_return")
            dd = st.get("max_drawdown")
            cells.append({
                "value": v,
                "ok": True,
                "total_return": round(float(total_return), 3) if isinstance(total_return, (int, float)) else None,
                "annual_return": _safe(st.get("annual_return")),
                "max_drawdown": round(float(dd), 3) if isinstance(dd, (int, float)) else None,
                "sharpe": _safe(st.get("sharpe_ratio")),
                "trade_count": r.get("trade_count", 0),
            })
        else:
            cells.append({"value": v, "ok": False, "error": r.get("error", "回测失败")})

    best = None
    ok_cells = [c for c in cells if c["ok"] and c.get("total_return") is not None]
    if ok_cells:
        best = max(ok_cells, key=lambda c: c["total_return"])

    data = {
        "success": len(ok_cells) > 0,
        "strategy_id": sid,
        "class_name": best_class,
        "param_name": body.param_name,
        "vt_symbol": body.vt_symbol,
        "start": body.start,
        "end": end,
        "cells": sorted(cells, key=lambda c: c["value"]),
        "best": best,
        "mode": "1d",
        "message": f"扫描 {len(cells)} 组参数" + (f"，最佳 {body.param_name}={best['value']}（总收益 {best['total_return']}%）" if best else "（无有效结果）"),
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


@router.post("/portfolio")
def portfolio_backtest(body: PortfolioRequest):
    """组合回测：同一策略在多标的上分别出信号，等权/自定义权重分配资金。

    说明：项目策略族基于 vn.py CtaTemplate，这里做组合回测采用「信号照搬」方案——
    每个标的独立运行该策略，用目标仓位驱动组合引擎，得到组合净值/回撤。
    """
    import sys as _sys

    symbols = [str(s) for s in body.vt_symbols if str(s).strip()]
    if len(symbols) < 2:
        raise HTTPException(status_code=400, detail="组合至少需要 2 个标的")
    symbols = symbols[:10]

    weights = body.weights
    if weights is None:
        weights = [1.0 / len(symbols)] * len(symbols)
    if len(weights) != len(symbols):
        raise HTTPException(status_code=400, detail="weights 长度必须与 vt_symbols 一致")
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

    futures = {pool.submit(_run_backtest, sid, {**cfg_base, "vt_symbol": s}): s for s in symbols}

    # 收集每个标的的日收益序列，按日期对齐后加权合成组合净值
    date_rets: dict[str, dict[str, float]] = {}
    symbol_class = None
    per_symbol = []
    for fut, s in futures.items():
        try:
            r = fut.result(timeout=300)
        except Exception as e:
            r = {"ok": False, "error": str(e)}
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
        per_symbol.append(
            {
                "vt_symbol": s,
                "ok": True,
                "class_name": r.get("class_name"),
                "total_return": round(float(r["stats"].get("total_return", 0) or 0), 3),
                "trade_count": r.get("trade_count", 0),
            }
        )

    if not date_rets:
        return {
            "success": False,
            "strategy_id": sid,
            "message": "组合中所有标的回测失败，请确认已同步行情数据",
            "per_symbol": per_symbol,
        }

    all_dates = sorted({d for srets in date_rets.values() for d in srets})
    comb_ret: dict[str, float] = {}
    for d in all_dates:
        acc = 0.0
        for s, srets in date_rets.items():
            idx = symbols.index(s)
            acc += float(weights[idx]) * srets.get(d, 0.0)
        comb_ret[d] = acc

    nav = 1.0
    navs: list[float] = []
    for d in all_dates:
        nav *= 1.0 + comb_ret.get(d, 0.0)
        navs.append(round(nav, 6))

    peak = 1.0
    max_dd = 0.0
    for n in navs:
        peak = max(peak, n)
        dd = n / peak - 1.0
        max_dd = min(max_dd, dd)

    returns = comb_ret
    avg = sum(returns.values()) / len(returns) if returns else 0.0
    std = (sum((r - avg) ** 2 for r in returns.values()) / max(1, len(returns) - 1)) ** 0.5
    sharpe = (avg / std * 252 ** 0.5) if std > 0 else 0.0
    total_ret = navs[-1] - 1.0 if navs else 0.0

    # 各标的权重展示
    weight_info = [
        {"vt_symbol": s, "weight": round(float(w), 4)}
        for s, w in zip(symbols, weights)
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
            "total_return": round(total_ret * 100, 3),
            "annual_return": round(((1 + total_ret) ** (252 / max(1, len(all_dates))) - 1) * 100, 3),
            "max_drawdown": round(max_dd * 100, 3),
            "sharpe_ratio": round(float(sharpe), 3),
            "total_trade_count": sum(p.get("trade_count", 0) for p in per_symbol if p.get("ok")),
        },
        "per_symbol": per_symbol,
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
    """纸面交易：用策略信号逻辑在最新日线上模拟持仓，输出持仓/成本/浮动盈亏/信号历史。

    方案：拉取该标的最近日线 → 用族策略参数计算信号（不做完整回测，只评估最新持仓状态），
    从信号的最后一笔触发点起模拟成本与浮动盈亏。适合快速看"如果现在按该策略持仓会怎样"。
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

    overrides = dict(body.fixed_params or {})
    setting = build_setting(strategy_cls, row, overrides)

    end_d = pd.Timestamp.today().normalize()
    start_d = (end_d - pd.Timedelta(days=int(body.lookback * 2.0))).strftime("%Y-%m-%d")
    df = _load_daily_df(body.vt_symbol, start_d, end_d.strftime("%Y-%m-%d"))
    if df is None or len(df) < 40:
        raise HTTPException(status_code=404, detail="本地库/免费源均无该标的足够日线，请先同步行情")

    df = df.sort_values("trade_date").reset_index(drop=True)
    close = df["close"].astype(float).to_numpy()
    high = df["high"].astype(float).to_numpy()
    low = df["low"].astype(float).to_numpy()
    dates = df["trade_date"].tolist()

    # 用族策略的公开信号方法（on_bar 简化）：若策略有 get_signal 辅助则用，否则用通用均线逻辑
    from rewritten_strategies import _family_helpers as fh

    fast = int(setting.get("fast_window", 5) or 5)
    slow = int(setting.get("slow_window", 20) or 20)
    fast_ma = fh.sma_series(close, fast)
    slow_ma = fh.sma_series(close, slow)

    # 逐根生成信号：快线上穿慢线=多，下穿=空
    signals: list[dict] = []
    position = 0  # 1 多 / -1 空 / 0 空仓
    last_entry_idx = None
    entry_price = None
    entry_date = None
    prev_cross = 0.0
    for i in range(len(close)):
        if i < 1 or fast_ma[i] == 0 or slow_ma[i] == 0:
            continue
        f, s = fast_ma[i], slow_ma[i]
        cross = 1.0 if f > s else (-1.0 if f < s else 0.0)
        if prev_cross != 0 and cross != prev_cross:
            # 交叉触发
            signals.append({
                "date": str(dates[i]),
                "price": round(float(close[i]), 3),
                "side": "buy" if cross > 0 else "short",
                "position_after": 1 if cross > 0 else -1,
            })
            position = 1 if cross > 0 else -1
            last_entry_idx = i
            entry_price = float(close[i])
            entry_date = str(dates[i])
        prev_cross = cross

    # 当前持仓状态
    latest_price = float(close[-1])
    unrealized = None
    if position != 0 and entry_price:
        unrealized = (latest_price - entry_price) / entry_price * 100 if position > 0 else (entry_price - latest_price) / entry_price * 100

    # 模拟权益曲线：以最近 N 日价格变化估算（无持仓时为现金）
    nav = [1.0]
    if position != 0 and entry_price and last_entry_idx is not None:
        for i in range(last_entry_idx, len(close)):
            r = (close[i] - entry_price) / entry_price if position > 0 else (entry_price - close[i]) / entry_price
            nav.append(1.0 + r)
    else:
        nav = [1.0, 1.0]

    return {
        "success": True,
        "strategy_id": sid,
        "class_name": row["class_name"],
        "archetype": row["archetype"],
        "vt_symbol": body.vt_symbol,
        "position": {1: "多", -1: "空", 0: "空仓"}.get(position),
        "position_code": position,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "latest_price": latest_price,
        "unrealized_pct": round(unrealized, 3) if unrealized is not None else 0.0,
        "signal_count": len(signals),
        "signals": signals[-12:],  # 最近 12 个信号
        "params_used": {k: setting.get(k) for k in ("fast_window", "slow_window", "fixed_size") if setting.get(k) is not None},
        "dates": [str(d) for d in dates[-(len(nav)):]],
        "nav": [round(v, 6) for v in nav],
        "capital": body.capital,
        "message": f"最新持仓: { {1:'多',-1:'空',0:'空仓'}[position] } · 浮动 {round(unrealized,2) if unrealized is not None else 0}% · 信号 {len(signals)} 次",
    }