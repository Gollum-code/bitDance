from __future__ import annotations

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyZscore(CtaTemplate):
    """z-score 均值回归族。

    源模板：12 均值回归（胜率100%）/ 18 均值回归分享 / 02,13,19,50,55 配对策略（单标价差近似）。
    逻辑：收盘价相对 slow_window 均线的偏离 z-score；z 低于下限买入、高于上限卖出。
    参数语义：fast_window=均线窗口，slow_window=z-score 窗口，signal_window=买入下界，atr_window=卖出上界。
    """

    author = "bitDance"

    fast_window: int = 20
    slow_window: int = 60
    signal_window: int = -2
    atr_window: int = 1
    fixed_size: int = 1

    zscore_value: float = 0.0
    ma_value: float = 0.0

    parameters = ["fast_window", "slow_window", "signal_window", "atr_window", "fixed_size"]
    variables = ["zscore_value", "ma_value", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.slow_window + self.fast_window)
        self.buy_limit: float = float(self.signal_window)
        self.sell_limit: float = float(self.atr_window)

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

        close_arr = self.am.close
        self.ma_value = H.sma(close_arr, self.fast_window)
        sub = close_arr - H.sma_series(close_arr, self.fast_window)
        self.zscore_value = H.zscore(sub, self.slow_window)

        if self.pos == 0:
            if self.zscore_value <= self.buy_limit:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.zscore_value >= self.sell_limit:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass