from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyValue(CtaTemplate):
    """价值/低估值族（财务因子的价格代理）。

    源模板：07 价值精选 / 23 祖鲁法则 / 31 低PB / 33 行业最大市值 / 71 CAPM+ROE / 85 便宜股 / 96 沪港银行 / 97 银行翻倍。
    说明：聚宽模板依赖 PE/PB/ROE 等财务数据，vn.py 日线回测无财务字段，
    此处以"长期均线下方回归"代理低估信号：价格回落至长期均线下方的深度越大越"便宜"。
    参数语义：fast_window=观察均线，slow_window=长期均线，signal_window=买入偏离阈值，
    atr_window=止损/止盈阈值窗口，atr_mult=偏离恢复卖出阈值。
    """

    author = "bitDance"

    fast_window: int = 20
    slow_window: int = 120
    signal_window: float = -0.08
    atr_window: int = 60
    atr_mult: float = -0.02
    fixed_size: int = 1

    deviation: float = 0.0
    ma_long: float = 0.0

    parameters = ["fast_window", "slow_window", "signal_window", "atr_window", "atr_mult", "fixed_size"]
    variables = ["deviation", "ma_long", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.slow_window + self.fast_window)
        self.buy_deviation: float = float(self.signal_window)
        self.sell_deviation: float = float(self.atr_mult)

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
            # 回归到接近长期均线（不再便宜）时卖出
            if self.deviation >= self.sell_deviation or self.deviation > 0.0:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass