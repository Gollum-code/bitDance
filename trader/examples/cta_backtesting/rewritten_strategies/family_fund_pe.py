from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyFundPe(CtaTemplate):
    """基金/指数估值调仓族（PE 区间代理）。

    源模板：65 8只基金按PE调仓 / 72 基金定投沪深300（PE 分位定投）。
    说明：聚宽用指数 PE 分位决定定投倍数，vn.py 无 PE；以"价格相对长期均线的
    偏离分位"代理估值：越低于长期均线定投越多（买入），越高清仓离场。
    参数语义：fast_window=短期均线，slow_window=长期均线，
    signal_window=高估卖出阈值，atr_window=低估加仓阈值。
    """

    author = "bitDance"

    fast_window: int = 20
    slow_window: int = 120
    signal_window: float = 0.03
    atr_window: float = -0.05
    fixed_size: int = 1

    deviation: float = 0.0
    ma_long: float = 0.0

    parameters = ["fast_window", "slow_window", "signal_window", "atr_window", "fixed_size"]
    variables = ["deviation", "ma_long", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.slow_window * 2)
        self.sell_deviation: float = float(self.signal_window)
        self.buy_deviation: float = float(self.atr_window)
        self.units: int = 0

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

        close = self.am.close
        self.ma_long = H.sma(close, self.slow_window)
        if np.isnan(self.ma_long) or self.ma_long < 1e-9:
            return
        self.deviation = float(close[-1] / self.ma_long - 1.0)

        if self.pos == 0:
            if self.deviation <= self.buy_deviation:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.deviation >= self.sell_deviation:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass