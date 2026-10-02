from __future__ import annotations

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData


class FamilyMacdTiming(CtaTemplate):
    """MACD 大盘择时族。

    源模板：76 MACD——大盘择时 / 08 MACD单因子多头 / 58 MACD金叉买入死叉卖出。
    逻辑：DIFF 上穿 DEA 全仓开多，DIFF 下穿 DEA 清仓；以 DIF 相对 0 轴强化信号。
    参数语义：fast_period=快线，slow_period=慢线，signal_period=信号线，fixed_size=每笔手数。
    """

    author = "bitDance"

    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    fixed_size: int = 1

    dif: float = 0.0
    dea: float = 0.0
    hist: float = 0.0

    parameters = ["fast_period", "slow_period", "signal_period", "fixed_size"]
    variables = ["dif", "dea", "hist", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.slow_period * 3)

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

        dif_arr, dea_arr, hist_arr = self.am.macd(
            self.fast_period, self.slow_period, self.signal_period, array=True
        )
        self.dif = dif_arr[-1]
        self.dea = dea_arr[-1]
        self.hist = hist_arr[-1]

        if self.pos == 0:
            if self.dif > self.dea:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.dif < self.dea:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass