from __future__ import annotations

import numpy as np
from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData


class RewrittenStrategy82(CtaTemplate):
    """Rewritten local vn.py strategy.

    Source: 82 次新+小市值+KAMA择时 轮动.py
    Archetype: ama_atr
    """

    author = "GitHub Copilot"

    fast_window: int = 5
    slow_window: int = 20
    signal_window: int = 9
    atr_window: int = 14
    atr_mult: float = 3.0
    fixed_size: int = 1

    fast_value: float = 0.0
    slow_value: float = 0.0
    signal_value: float = 0.0
    stop_price: float = 0.0

    parameters = ["fast_window", "slow_window", "signal_window", "atr_window", "atr_mult", "fixed_size"]
    variables = ["fast_value", "slow_value", "signal_value", "stop_price", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(80)
        self.intra_trade_high: float = 0.0
        self.intra_trade_low: float = 0.0

    def on_init(self) -> None:
        self.write_log("策略初���化")

    def on_start(self) -> None:
        self.write_log("策略启动")

    def on_stop(self) -> None:
        self.write_log("策略停止")

    def on_bar(self, bar: BarData) -> None:
        self.cancel_all()
        self.am.update_bar(bar)
        if not self.am.inited:
            return

        kama = self.am.kama(self.fast_window, array=True)
        self.fast_value = float(kama[-1])
        self.slow_value = float(np.nanstd(kama[-self.slow_window:]))
        atr = float(self.am.atr(self.atr_window))

        if np.isnan(self.fast_value) or np.isnan(atr) or atr <= 0:
            return

        diff = float(kama[-1] - kama[-2])
        threshold = self.slow_value

        if self.pos == 0:
            if diff > threshold:
                self.buy(bar.close_price * 1.01, self.fixed_size)
                self.intra_trade_high = bar.high_price
            elif -diff > threshold:
                self.short(bar.close_price * 0.99, self.fixed_size)
                self.intra_trade_low = bar.low_price
        elif self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.stop_price = self.intra_trade_high - self.atr_mult * atr
            if bar.close_price <= self.stop_price or -diff > threshold:
                self.sell(bar.close_price * 0.99, abs(self.pos))
        else:
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
            self.stop_price = self.intra_trade_low + self.atr_mult * atr
            if bar.close_price >= self.stop_price or diff > threshold:
                self.cover(bar.close_price * 1.01, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass
