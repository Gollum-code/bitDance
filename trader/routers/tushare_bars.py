"""Convert TuShare Pro `daily` DataFrame rows to vn.py BarData and persist."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from vnpy.trader.utility import ZoneInfo


def _exchange_from_suffix(suffix: str) -> Exchange:
    exchange_map = {
        "SH": Exchange.SSE,
        "SZ": Exchange.SZSE,
        "BJ": Exchange.BSE,
        "CFX": Exchange.CFFEX,
        "SHF": Exchange.SHFE,
        "ZCE": Exchange.CZCE,
        "DCE": Exchange.DCE,
        "INE": Exchange.INE,
        "GFE": Exchange.GFEX,
    }
    return exchange_map.get(suffix, Exchange.SSE)


def bars_from_tushare_daily_df(df: pd.DataFrame, gateway_name: str = "TUSHARE") -> list[BarData]:
    """Build BarData list from TuShare `daily` columns (ts_code, trade_date, OHLC, vol, amount)."""
    if df is None or df.empty:
        return []

    required = {"ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame 缺少列: {sorted(missing)}")

    bars: list[BarData] = []
    for _, row in df.iterrows():
        ts_code = str(row["ts_code"])
        symbol, exchange_str = ts_code.split(".")
        exchange = _exchange_from_suffix(exchange_str)

        td = row["trade_date"]
        if isinstance(td, str):
            trade_date = td.replace("-", "")[:8]
        else:
            trade_date = str(int(td))
        dt = datetime.strptime(trade_date, "%Y%m%d")
        dt = dt.replace(tzinfo=ZoneInfo("Asia/Shanghai"))

        bar = BarData(
            symbol=symbol,
            exchange=exchange,
            datetime=dt,
            interval=Interval.DAILY,
            volume=float(row["vol"] or 0),
            turnover=float(row["amount"] or 0),
            open_interest=0,
            open_price=float(row["open"] or 0),
            high_price=float(row["high"] or 0),
            low_price=float(row["low"] or 0),
            close_price=float(row["close"] or 0),
            gateway_name=gateway_name,
        )
        bars.append(bar)

    return bars


def save_bars_to_database(bars: list[BarData]) -> int:
    if not bars:
        return 0
    database = get_database()
    database.save_bar_data(bars)
    return len(bars)
