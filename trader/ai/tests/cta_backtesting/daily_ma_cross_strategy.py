from __future__ import annotations

from typing import Optional

from vnpy_ctastrategy import CtaTemplate, BarData, OrderData, TradeData, ArrayManager


class DailyMACrossStrategy(CtaTemplate):
    """最小可运行的日线均线交叉示例策略。"""

    author = "GitHub Copilot"

    fast_window: int = 5
    slow_window: int = 10
    fixed_size: int = 1

    fast_ma: float = 0.0
    slow_ma: float = 0.0
    bar_count: int = 0

    parameters = ["fast_window", "slow_window", "fixed_size"]
    variables = ["bar_count", "fast_ma", "slow_ma", "pos"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        # 日线 demo 只需要较小窗口即可，避免 63 根数据下始终不触发。
        self.am: ArrayManager = ArrayManager(20)
        self._prev_fast_ma: Optional[float] = None
        self._prev_slow_ma: Optional[float] = None

    def on_init(self) -> None:
        self.write_log("策略初始化")

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

        # 生成金叉/死叉信号
        if self.fast_ma > self.slow_ma:
            cross_up = True
        else:
            cross_up = False

        if self.pos == 0 and cross_up:
            self.buy(bar.close_price + 1, self.fixed_size)
        elif self.pos > 0 and not cross_up:
            self.sell(bar.close_price - 1, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass


