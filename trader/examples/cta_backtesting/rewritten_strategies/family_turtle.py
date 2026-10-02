from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyTurtle(CtaTemplate):
    """海龟交易族（唐奇安通道突破 + ATR 止损）。

    源模板：22 海龟交易法则升级版 / 49 海龟克隆优化。
    逻辑：突破 fast_window 高点开多，跌破 slow_window 低点平多；
    持仓后以 ATR 通道止损（close 跌破开仓价减 atr_mult*ATR 平多）。
    参数语义：fast_window=入场通道，slow_window=出场通道，atr_window=ATR 窗口，atr_mult=止损倍数。
    """

    author = "bitDance"

    fast_window: int = 20
    slow_window: int = 10
    atr_window: int = 20
    atr_mult: float = 3.0
    fixed_size: int = 1

    entry_price: float = 0.0
    stop_price: float = 0.0
    atr_value: float = 0.0

    parameters = ["fast_window", "slow_window", "atr_window", "atr_mult", "fixed_size"]
    variables = ["entry_price", "stop_price", "atr_value", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(max(self.fast_window, self.atr_window) * 3)

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

        entry_high, _ = H.donchian_break(self.am.high, self.am.low, self.fast_window)
        _, exit_low = H.donchian_break(self.am.high, self.am.low, self.slow_window)
        self.atr_value = H.atr(self.am.high, self.am.low, self.am.close, self.atr_window)

        if self.pos == 0:
            if bar.close_price > entry_high:
                self.buy(bar.close_price, self.fixed_size)
                self.entry_price = bar.close_price
        elif self.pos > 0:
            self.stop_price = max(
                self.entry_price - self.atr_mult * self.atr_value if self.entry_price else bar.close_price,
                self.entry_price - self.atr_mult * self.atr_value,
            )
            if bar.close_price < exit_low or bar.close_price <= self.entry_price - self.atr_mult * self.atr_value:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass