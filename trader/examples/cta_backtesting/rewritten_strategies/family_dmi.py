from __future__ import annotations

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData


class FamilyDmi(CtaTemplate):
    """DMI 趋向指标择时族。

    源模板：79 DMI——大盘择时。
    逻辑：ADX 抬升且 +DI > -DI 开多；ADX 回落且 +DI < -DI 平多。
    参数语义：fast_window=周期，atr_mult=ADX 上升判定所需最小增量。
    """

    author = "bitDance"

    fast_window: int = 18
    atr_mult: float = 1.0
    fixed_size: int = 1

    adx_value: float = 0.0
    pdi_value: float = 0.0
    mdi_value: float = 0.0

    parameters = ["fast_window", "atr_mult", "fixed_size"]
    variables = ["adx_value", "pdi_value", "mdi_value", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.fast_window * 4)
        self.prev_adx: float = 0.0

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

        adx_arr = self.am.adx(self.fast_window, array=True)
        pdi_arr = self.am.plus_di(self.fast_window, array=True)
        mdi_arr = self.am.minus_di(self.fast_window, array=True)

        self.adx_value = adx_arr[-1]
        self.pdi_value = pdi_arr[-1]
        self.mdi_value = mdi_arr[-1]

        adx_rising = self.adx_value > self.prev_adx
        bull = adx_rising and self.pdi_value > self.mdi_value
        bear = (not adx_rising) and self.pdi_value < self.mdi_value

        if self.pos == 0:
            if bull:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if bear:
                self.sell(bar.close_price, abs(self.pos))

        self.prev_adx = self.adx_value
        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass