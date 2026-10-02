from __future__ import annotations

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilySmaTrend(CtaTemplate):
    """多均线多头排列族。

    源模板：15 基于多期限的选股策略 / 54 中长线买入卖出点选择 / 89 简单多均线择时（test1）。
    逻辑：短期>中期>长期均线严格多头排列（均线多头鬃）开多，
    短期均线下穿中期均线（背离）平多。
    参数语义：fast_window=短期均线，slow_window=中期均线，signal_window=长期均线。
    """

    author = "bitDance"

    fast_window: int = 5
    slow_window: int = 10
    signal_window: int = 20
    fixed_size: int = 1

    ma_fast: float = 0.0
    ma_mid: float = 0.0
    ma_slow: float = 0.0

    parameters = ["fast_window", "slow_window", "signal_window", "fixed_size"]
    variables = ["ma_fast", "ma_mid", "ma_slow", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.signal_window * 3)

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
        self.ma_fast = H.sma(close, self.fast_window)
        self.ma_mid = H.sma(close, self.slow_window)
        self.ma_slow = H.sma(close, self.signal_window)

        if self.pos == 0:
            if self.ma_fast > self.ma_mid > self.ma_slow:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.ma_fast < self.ma_mid:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass