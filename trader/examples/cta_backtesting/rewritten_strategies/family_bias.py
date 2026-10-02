from __future__ import annotations

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyBias(CtaTemplate):
    """BIAS 乖离率择时族。

    源模板：21 果核量化 BIAS_QL 乖离率策略指数择时。
    逻辑：计算 N 日乖离率，乖离率上穿其 M 日均线开多，下穿平多。
    参数语义：fast_window=N（乖离率窗口），slow_window=M（乖离率均线窗口）。
    """

    author = "bitDance"

    fast_window: int = 6
    slow_window: int = 6
    fixed_size: int = 1

    bias_value: float = 0.0
    bias_ma: float = 0.0

    parameters = ["fast_window", "slow_window", "fixed_size"]
    variables = ["bias_value", "bias_ma", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager((self.fast_window + self.slow_window) * 3)
        self.prev_bias: float = 0.0
        self.prev_bias_ma: float = 0.0

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
        self.bias_value = H.bias_percent(close, self.fast_window)

        # 乖离率序列的均线
        bias_series = (close / H.sma_series(close, self.fast_window) - 1.0) * 100.0
        self.bias_ma = H.sma(bias_series, self.slow_window)

        if self.pos == 0:
            if self.prev_bias <= self.prev_bias_ma and self.bias_value > self.bias_ma:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.prev_bias >= self.prev_bias_ma and self.bias_value < self.bias_ma:
                self.sell(bar.close_price, abs(self.pos))

        self.prev_bias = self.bias_value
        self.prev_bias_ma = self.bias_ma
        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass