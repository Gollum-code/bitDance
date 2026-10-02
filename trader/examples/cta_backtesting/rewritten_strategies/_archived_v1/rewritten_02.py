from __future__ import annotations

import numpy as np
from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData


class RewrittenStrategy02(CtaTemplate):
    """Rewritten local vn.py strategy.

    Source: 02 我好像破解了聚宽擂台排第一的策略？！.py
    Archetype: zscore
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

        close = self.am.close[-self.slow_window:]
        mean = float(np.mean(close))
        std = float(np.std(close))
        if std <= 0:
            return

        z = (float(close[-1]) - mean) / std
        self.signal_value = z

        if self.pos == 0:
            if z > 1:
                self.short(bar.close_price * 0.99, self.fixed_size)
            elif z < -1:
                self.buy(bar.close_price * 1.01, self.fixed_size)
        elif self.pos > 0 and z >= 0:
            self.sell(bar.close_price * 0.99, abs(self.pos))
        elif self.pos < 0 and z <= 0:
            self.cover(bar.close_price * 1.01, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass
