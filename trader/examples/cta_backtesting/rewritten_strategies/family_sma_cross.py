from __future__ import annotations

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData


class FamilySmaCross(CtaTemplate):
    """双均线金叉/死叉族。

    源模板：09 商品期货双均线 / 66 MA10买MA20卖 / 83 沪深300ETF-1060 / 86 5日穿10日 / 90 向导MA。
    逻辑：fast_window 上穿 slow_window 开多，下穿平多。
    参数语义：fast_window=快线，slow_window=慢线，fixed_size=每笔手数。
    """

    author = "bitDance"

    fast_window: int = 5
    slow_window: int = 20
    fixed_size: int = 1

    fast_ma: float = 0.0
    slow_ma: float = 0.0

    parameters = ["fast_window", "slow_window", "fixed_size"]
    variables = ["fast_ma", "slow_ma", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.slow_window + 5)

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

        self.fast_ma = self.am.sma(self.fast_window)
        self.slow_ma = self.am.sma(self.slow_window)

        if self.pos == 0:
            if self.fast_ma > self.slow_ma:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.fast_ma < self.slow_ma:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass
