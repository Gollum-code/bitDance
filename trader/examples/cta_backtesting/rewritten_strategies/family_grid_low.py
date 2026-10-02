from __future__ import annotations

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyGridLow(CtaTemplate):
    """低吸网格族。

    源模板：11 酒股地中短线策略 / 14 抗击熊市的中短期低市值策略。
    逻辑：价格低于短期均线时按偏离程度分档买入（越跌买越多），
    盈利达目标（ret>profit_step）时按挡位派卖。
    参数语义：fast_window=参考均线窗口，signal_window=单档买入比例，
    atr_window=分档间距（%），atr_mult=单档止盈（%）。
    """

    author = "bitDance"

    fast_window: int = 10
    signal_window: float = 0.2
    atr_window: float = 0.05
    atr_mult: float = 0.05
    fixed_size: int = 100

    ma_ref: float = 0.0
    entry_price: float = 0.0
    grid_index: int = 0

    parameters = ["fast_window", "signal_window", "atr_window", "atr_mult", "fixed_size"]
    variables = ["ma_ref", "entry_price", "grid_index", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.fast_window * 4)
        self.step_profit: float = float(self.atr_mult)

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
        self.ma_ref = H.sma(close, self.fast_window)
        price = bar.close_price

        if self.pos == 0:
            if price < self.ma_ref:
                self.buy(price, max(self.fixed_size, 1))
                self.entry_price = price
                self.grid_index = 1
        elif self.pos > 0:
            # 回撤加仓：跌破均线更多档位加仓
            if price < self.ma_ref * (1 - self.grid_index * float(self.atr_window)):
                self.buy(price, max(self.fixed_size, 1))
                self.grid_index += 1
            # 止盈：相对均价上涨达单档止盈，派卖一格
            elif self.entry_price > 0 and price >= self.entry_price * (1 + self.grid_index * self.step_profit):
                self.sell(price, max(int(abs(self.pos) / max(self.grid_index, 1)) or 1, 1))
                self.grid_index -= 1 if self.grid_index > 0 else 0

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        if trade.direction.value == "买入" and trade.price > 0:
            self.entry_price = self.entry_price or trade.price

    def on_order(self, order: OrderData) -> None:
        pass