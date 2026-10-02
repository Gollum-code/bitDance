from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData


class FamilyTrixRsi(CtaTemplate):
    """低估值 + TRIX + RSI 低回撤族。

    源模板：42 低估值+TRIX+RSI 低回撤策略。
    逻辑：TRIX 上穿其均线且 RSI 未超买时开多；TRIX 下穿或 RSI 超买回落时平多。
    参数语义：fast_window=TRIX 窗口，slow_window=TRIX 均线窗口，signal_window=RSI 窗口，
    atr_mult=RSI 超买阈值。
    """

    author = "bitDance"

    fast_window: int = 12
    slow_window: int = 9
    signal_window: int = 14
    atr_mult: float = 70.0
    fixed_size: int = 1

    trix_value: float = 0.0
    trix_ma: float = 0.0
    rsi_value: float = 0.0

    parameters = ["fast_window", "slow_window", "signal_window", "atr_mult", "fixed_size"]
    variables = ["trix_value", "trix_ma", "rsi_value", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.fast_window * 5)
        self.rsi_overbought: float = float(self.atr_mult)
        self.prev_trix: float = 0.0
        self.prev_ma: float = 0.0

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

        trix_arr = self.am.trix(self.fast_window, array=True)
        self.trix_value = trix_arr[-1]
        # TRIX 自身的短均线
        self.trix_ma = float(np.mean(trix_arr[-self.slow_window:]))
        self.rsi_value = self.am.rsi(self.signal_window)

        if self.pos == 0:
            if self.prev_trix <= self.prev_ma and self.trix_value > self.trix_ma and self.rsi_value < self.rsi_overbought:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.trix_value < self.trix_ma or self.rsi_value > self.rsi_overbought:
                self.sell(bar.close_price, abs(self.pos))

        self.prev_trix = self.trix_value
        self.prev_ma = self.trix_ma
        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass