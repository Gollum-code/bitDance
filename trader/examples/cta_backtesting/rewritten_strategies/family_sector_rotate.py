from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilySectorRotate(CtaTemplate):
    """行业/板块轮动族（相对强度 proxy）。

    源模板：68 板块轮动不动？ / 81 申万行业轮动策略。
    说明：原模板在多个行业 ETF 之间做相对强度轮动；vn.py 单标的回测退化为一支
    "相对自身长短期动量的轮动选择"：长期动量为胜出行业特征、短期回调即入场，
    破位即切换出场。保留"动量切面"思路（周线重估一次）。
    参数语义：fast_window=短期动量窗口，slow_window=长期动量窗口，
    signal_window=入场阈值，atr_window=趋势过滤窗口。
    """

    author = "bitDance"

    fast_window: int = 5
    slow_window: int = 20
    signal_window: float = 0.0
    atr_window: int = 10
    fixed_size: int = 1

    short_mom: float = 0.0
    long_mom: float = 0.0

    parameters = ["fast_window", "slow_window", "signal_window", "atr_window", "fixed_size"]
    variables = ["short_mom", "long_mom", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.slow_window * 3)
        self.entry_threshold: float = float(self.signal_window)

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
        if len(close) <= self.slow_window:
            return

        self.long_mom = float(close[-1] / close[-self.slow_window] - 1.0)
        self.short_mom = float(close[-1] / close[-self.fast_window] - 1.0)

        # 趋势确认：价格在 atr_window 均线上方
        above_ma = bar.close_price > H.sma(close, self.atr_window)

        if self.pos == 0:
            if self.long_mom > max(self.entry_threshold, 0.0) and self.short_mom > 0.0 and above_ma:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.long_mom < 0.0 or not above_ma:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass