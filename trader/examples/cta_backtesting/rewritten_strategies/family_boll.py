from __future__ import annotations

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyBoll(CtaTemplate):
    """布林带突破族。

    源模板：45 布林带策略 / 52 布林带1。
    逻辑：收盘价上穿上轨开多，跌破下轨平多。
    参数语义：boll_window=布林窗口，boll_dev=带宽倍数，fixed_size=每笔手数。
    """

    author = "bitDance"

    boll_window: int = 20
    boll_dev: float = 2.0
    fixed_size: int = 1

    boll_upper: float = 0.0
    boll_lower: float = 0.0
    boll_mid: float = 0.0

    parameters = ["boll_window", "boll_dev", "fixed_size"]
    variables = ["boll_upper", "boll_lower", "boll_mid", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.boll_window * 3)

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

        self.boll_upper, self.boll_lower = self.am.boll(self.boll_window, self.boll_dev)
        self.boll_mid = H.sma(self.am.close, self.boll_window)

        if self.pos == 0:
            if bar.close_price > self.boll_upper:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if bar.close_price < self.boll_lower:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass
