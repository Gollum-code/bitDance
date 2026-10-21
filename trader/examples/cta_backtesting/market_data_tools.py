"""行情数据工具：体检、分段拉取、修复、按需同步。

供 `scripts/repair_market_data.py` 与 `scripts/collect_portfolio_metrics.py` 共用，
避免「复现脚本依赖别人先手动灌数据」的问题。

设计原则：
  - 免费源单次最多 640 根，因此按自然年切段拉取再合并去重
  - 写入前必须通过完整性校验，避免把坏数据静默写进库
  - `ensure_symbol_data` 是幂等的：数据已覆盖区间且体检通过就跳过
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from vnpy.trader.constant import Exchange, Interval

JUMP_LIMIT = 0.50
FREE_SOURCE_MAX_BARS = 640
# 相邻两根日线的最大日历间隔。A 股春节休市约 10 天，个股停牌可能更久；
# 取 45 天可容忍停牌，同时能抓住「分段拉取失败导致整年缺失」这类空洞。
MAX_CALENDAR_GAP_DAYS = 45

_EXCHANGE_PREFIX = {"SSE": "sh", "SZSE": "sz", "BSE": "bj"}


def to_tx(symbol: str, exchange: Exchange) -> str:
    """本地代码 → 腾讯行情代码（如 600519.SSE → sh600519）。"""
    return f"{_EXCHANGE_PREFIX[exchange.value]}{symbol}"


def build_windows(start_year: int = 2018) -> list[tuple[str, str]]:
    """按自然年切段。A 股每年约 243 个交易日，远小于接口 640 根上限。"""
    this_year = datetime.now().year
    return [(f"{y}-01-01", f"{y + 1}-01-01") for y in range(start_year, this_year + 1)]


def fetch_chunked(
    tx: str,
    windows: list[tuple[str, str]] | None = None,
    retries: int = 3,
    sleep_s: float = 0.2,
) -> pd.DataFrame:
    """分段拉取真实前复权日线并合并去重。单段失败重试，最终失败只告警不中断。"""
    from routers.free_market import fetch_daily

    windows = windows or build_windows()
    frames: list[pd.DataFrame] = []
    for start, end in windows:
        for attempt in range(retries):
            try:
                df = fetch_daily(tx, start, end)
                if df is not None and not df.empty:
                    frames.append(df)
                    break
                if attempt == retries - 1:
                    print(f"    {start}~{end}: 空")
            except Exception as e:
                if attempt == retries - 1:
                    print(f"    {start}~{end}: 失败 {type(e).__name__}")
                else:
                    time.sleep(1.0 + attempt)
        time.sleep(sleep_s)

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset="trade_date", keep="last")
    return merged.sort_values("trade_date").reset_index(drop=True)


def _max_calendar_gap(dates) -> int:
    """相邻日期之间的最大日历天数差；用于发现整段缺失。"""
    s = pd.to_datetime(pd.Series(list(dates)), errors="coerce").dropna().sort_values()
    if len(s) < 2:
        return 0
    gaps = s.diff().dt.days.dropna()
    return int(gaps.max()) if len(gaps) else 0


def validate_frame(df: pd.DataFrame) -> tuple[bool, str]:
    """完整性校验：非正价 / OHLC 不自洽 / 异常跳变 / 整段缺失。"""
    if df is None or df.empty:
        return False, "无数据"
    c = df["close"].astype(float).to_numpy()
    o = df["open"].astype(float).to_numpy()
    h = df["high"].astype(float).to_numpy()
    low = df["low"].astype(float).to_numpy()
    if np.any(c <= 0) or np.any(o <= 0) or np.any(h <= 0) or np.any(low <= 0):
        return False, f"存在非正价格（close<=0: {int((c <= 0).sum())}）"
    bad_ohlc = int(((h < low) | (h < c) | (low > c) | (o > h) | (o < low)).sum())
    if bad_ohlc:
        return False, f"OHLC 不自洽 {bad_ohlc} 根"
    rets = np.diff(c) / c[:-1]
    jumps = int((np.abs(rets) > JUMP_LIMIT).sum())
    if jumps:
        return False, f"异常跳变 {jumps} 处"
    gap = _max_calendar_gap(df["trade_date"])
    if gap > MAX_CALENDAR_GAP_DAYS:
        return False, f"存在 {gap} 天数据空洞（疑似分段拉取缺失）"
    return True, f"{len(df)} 根，{df['trade_date'].iloc[0]}~{df['trade_date'].iloc[-1]}"


def diagnose_bars(bars: list) -> dict:
    """对已入库的 BarData 序列做体检。"""
    if not bars:
        return {"n": 0, "lo": 0.0, "hi": 0.0, "nonpos": 0, "ohlc_bad": 0, "jumps": 0,
                "max_gap_days": 0, "bad": True}
    c = np.array([x.close_price for x in bars], dtype=float)
    h = np.array([x.high_price for x in bars], dtype=float)
    low = np.array([x.low_price for x in bars], dtype=float)
    o = np.array([x.open_price for x in bars], dtype=float)
    nonpos = int((c <= 0).sum())
    ohlc_bad = int(((h < low) | (h < c) | (low > c) | (o > h) | (o < low)).sum())
    rets = np.diff(c) / np.where(np.abs(c[:-1]) > 1e-12, c[:-1], 1.0)
    jumps = int((np.abs(rets) > JUMP_LIMIT).sum())
    gap = _max_calendar_gap([x.datetime for x in bars])
    return {
        "n": len(c),
        "lo": float(c.min()),
        "hi": float(c.max()),
        "nonpos": nonpos,
        "ohlc_bad": ohlc_bad,
        "jumps": jumps,
        "max_gap_days": gap,
        "bad": bool(nonpos or ohlc_bad or jumps or gap > MAX_CALENDAR_GAP_DAYS),
    }


def _overview_row(db, symbol: str, exchange: Exchange):
    for b in db.get_bar_overview():
        if b.symbol == symbol and b.exchange == exchange and b.interval == Interval.DAILY:
            return b
    return None


def diagnose_symbol(db, symbol: str, exchange: Exchange) -> dict:
    b = _overview_row(db, symbol, exchange)
    if b is None:
        return {"symbol": symbol, "exchange": exchange, "n": 0, "lo": 0.0, "hi": 0.0,
                "nonpos": 0, "ohlc_bad": 0, "jumps": 0, "bad": True}
    bars = db.load_bar_data(symbol, exchange, Interval.DAILY, b.start, b.end)
    return {"symbol": symbol, "exchange": exchange, **diagnose_bars(bars)}


def diagnose_all(db) -> list[dict]:
    rows = []
    for b in db.get_bar_overview():
        bars = db.load_bar_data(b.symbol, b.exchange, b.interval, b.start, b.end)
        rows.append({"symbol": b.symbol, "exchange": b.exchange, "interval": b.interval,
                     **diagnose_bars(bars)})
    return rows


def coverage_ok(bars: list, start: str, end: str, tolerance_days: int = 10) -> bool:
    """首末 bar 是否覆盖请求区间（给节假日/停牌留容差）。"""
    if not bars:
        return False
    first = bars[0].datetime.date()
    last = bars[-1].datetime.date()
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    return first <= s + timedelta(days=tolerance_days) and last >= e - timedelta(days=tolerance_days)


def sync_symbol(
    db,
    symbol: str,
    exchange: Exchange,
    start_year: int = 2021,
    verbose: bool = True,
) -> tuple[int, str]:
    """强制重拉并覆盖某标的的全部日线。校验不通过则抛错且不改动库。"""
    from routers.tushare_bars import bars_from_tushare_daily_df, save_bars_to_database

    tx = to_tx(symbol, exchange)
    if verbose:
        print(f"  [SYNC] {symbol}.{exchange.value} ({tx})")
    df = fetch_chunked(tx, build_windows(start_year))
    ok, msg = validate_frame(df)
    if not ok:
        raise RuntimeError(f"{symbol}.{exchange.value} 拉取数据未通过校验：{msg}")
    db.delete_bar_data(symbol, exchange, Interval.DAILY)
    save_bars_to_database(bars_from_tushare_daily_df(df))
    if verbose:
        print(f"  [OK] {msg}")
    return len(df), msg


def ensure_symbol_data(
    db,
    symbol: str,
    exchange: Exchange,
    start: str,
    end: str,
    start_year: int = 2021,
) -> dict:
    """确保某标的有干净且覆盖区间的日线；已满足则跳过（幂等）。"""
    b = _overview_row(db, symbol, exchange)
    if b is not None:
        bars = db.load_bar_data(symbol, exchange, Interval.DAILY, b.start, b.end)
        d = diagnose_bars(bars)
        if not d["bad"] and coverage_ok(bars, start, end):
            return {"synced": False, **d}

    n, msg = sync_symbol(db, symbol, exchange, start_year=start_year)
    return {"synced": True, "n": n, "msg": msg}
