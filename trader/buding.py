from datetime import datetime
from collections.abc import Callable
from copy import deepcopy
import pandas as pd
from pandas import DataFrame
import tushare as ts

from vnpy.trader.setting import SETTINGS
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import TickData, HistoryRequest
from vnpy.trader.utility import round_to, ZoneInfo
from vnpy_tushare.tushare_datafeed import TushareDatafeed, to_ts_symbol, to_ts_asset, CHINA_TZ

"""
获取tick信息，好像没用
"""




def query_tick_history(self, req: HistoryRequest, output: Callable = print) -> list[TickData]:
    """查询tick数据（作为 TushareDatafeed 的实例方法/补丁使用）"""
    if not self.inited:
        self.init(output)

    symbol: str = req.symbol
    exchange: Exchange = req.exchange
    start: datetime = req.start
    end: datetime = req.end

    ts_symbol: str | None = to_ts_symbol(symbol, exchange)
    if not ts_symbol:
        output(f"不支持的交易所：{exchange}")
        return []

    asset: str | None = to_ts_asset(symbol, exchange)
    if not asset:
        output(f"不支持的资产类型：{symbol}.{exchange}")
        return []

    try:
        # Tushare pro_tick 按交易日查询，逐日拉取 start~end 区间
        ticks: list[TickData] = []
        cur = start
        while cur <= end:
            trade_date: str = cur.strftime("%Y%m%d")
            df = ts.pro_tick(ts_code=ts_symbol, trade_date=trade_date)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    time_str: str = f"{trade_date} {row['time']}"
                    try:
                        dt: datetime = datetime.strptime(time_str, "%Y%m%d %H:%M:%S.%f")
                    except ValueError:
                        dt = datetime.strptime(time_str, "%Y%m%d %H:%M:%S")
                    dt = dt.replace(tzinfo=CHINA_TZ)

                    tick: TickData = TickData(
                        symbol=symbol,
                        exchange=exchange,
                        datetime=dt,
                        last_price=row["price"],
                        bid_price_1=row.get("bid", 0),
                        ask_price_1=row.get("ask", 0),
                        bid_volume_1=row.get("bid_vol", 0),
                        ask_volume_1=row.get("ask_vol", 0),
                        volume=row["vol"],
                        turnover=row["amount"],
                        open_interest=row.get("oi", 0),
                        gateway_name="TS"
                    )
                    ticks.append(tick)
            # 跳到下一交易日（按自然日+1近似）
            cur = cur + pd.Timedelta(days=1)
    except Exception as ex:
        output(f"获取 Tick 数据失败：{ex}")
        return []

    return ticks

