from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData


class FamilyGftd(CtaTemplate):
    """GFTD 九转序列族。

    源模板：78 GFTD第二版。
    逻辑：跟踪 DeMark 九转序列——连续 n1 根收盘价相对前第 n2 根的方向计数；
    买入结构（连续收盘价 < 前第 n2 根低价）达到 buy_count 触发买入，
    卖出结构（连续收盘价 > 前第 n2 根高价）达到 sell_count 触发卖出。
    参数语义：fast_window=n1（对比位移），slow_window=n2（位移），
    signal_window=结构计数阈值，atr_mult=附加止盈倍数。
    """

    author = "bitDance"

    fast_window: int = 4
    slow_window: int = 4
    signal_window: int = 9
    atr_mult: float = 2.0
    fixed_size: int = 1

    buy_count: int = 0
    sell_count: int = 0
    state: str = "empty"

    parameters = ["fast_window", "slow_window", "signal_window", "atr_mult", "fixed_size"]
    variables = ["buy_count", "sell_count", "state", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(max(self.slow_window, self.signal_window) * 3)
        self.lookback: int = int(self.fast_window)

    def on_init(self) -> None:
        self.write_log("策略初始化")
        self.load_bar(10)

    def on_start(self) -> None:
        self.write_log("策略启动")

    def on_stop(self) -> None:
        self.write_log("策略停止")

    def on_bar(self, bar: BarData) -> None:
        self.cancel_all()
        self.am.update_bar(bar)
        if not self.am.inited:
            return

        close, high, low = self.am.close, self.am.high, self.am.low
        ref = int(self.slow_window)
        if len(close) <= ref:
            return

        # 结构计数：up（连续 收盘> 前ref根低点） / down（收盘< 前ref根高点）
        cur_close = close[-1]
        if self.buy_count == 0 and self.sell_count == 0:
            if cur_close < low[-ref - 1]:
                self.buy_count = 1
            elif cur_close > high[-ref - 1]:
                self.sell_count = 1
        else:
            if self.buy_count > 0:
                if cur_close < low[-ref - 1]:
                    self.buy_count += 1
                else:
                    self.buy_count = 0
            if self.sell_count > 0:
                if cur_close > high[-ref - 1]:
                    self.sell_count += 1
                else:
                    self.sell_count = 0

        self.state = (
            "buy_count" if self.buy_count >= self.signal_window
            else "sell_count" if self.sell_count >= self.signal_window
            else "empty"
        )

        if self.pos == 0:
            if self.state == "buy_count":
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.state == "sell_count" or cur_close < low[-ref - 1]:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass