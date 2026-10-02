from __future__ import annotations

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData


class FamilyEmaCross(CtaTemplate):
    """EMA 双均线交叉族。

    源模板：46 Get API 新技能（EMA交叉）。
    逻辑：快线 EMA 上穿慢线 EMA 开多，下穿平多。
    参数语义：fast_window=快线，slow_window=慢线，fixed_size=每笔手数。
    """

    author = "bitDance"

    fast_window: int = 5
    slow_window: int = 20
    fixed_size: int = 1

    fast_ema: float = 0.0
    slow_ema: float = 0.0

    parameters = ["fast_window", "slow_window", "fixed_size"]
    variables = ["fast_ema", "slow_ema", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.slow_window * 3)

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

        self.fast_ema = self.am.ema(self.fast_window)
        self.slow_ema = self.am.ema(self.slow_window)

        if self.pos == 0:
            if self.fast_ema > self.slow_ema:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.fast_ema < self.slow_ema:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass