from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilySmallcap(CtaTemplate):
    """小市值/次新轮动族（低价+小波 proxy）。

    源模板：14 低市值 / 25 简单市值轮动 / 59 小市值轮动（PE>0） / 82 次新+小市值+KAMA。
    说明：vn.py 无市值数据，以"低价（价格处于长期区间低位）+ 低波动 + 放量启动"
    代理小市值特征；按周期做再平衡轮动（模板的定期调仓思路）。
    参数语义：fast_window=再平衡周期，slow_window=区间窗口，
    signal_window=量能放大倍数，atr_window=波动过滤窗口。
    """

    author = "bitDance"

    fast_window: int = 20
    slow_window: int = 120
    signal_window: float = 1.2
    atr_window: int = 10
    fixed_size: int = 1

    price_position: float = 0.0
    vol_ratio: float = 0.0

    parameters = ["fast_window", "slow_window", "signal_window", "atr_window", "fixed_size"]
    variables = ["price_position", "vol_ratio", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.slow_window * 2)
        self.volume_surge: float = float(self.signal_window)
        self.bar_since_rebalance: int = 0

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
        if len(close) < self.slow_window:
            return

        lo = float(np.min(close[-self.slow_window:]))
        hi = float(np.max(close[-self.slow_window:]))
        self.price_position = float((close[-1] - lo) / (hi - lo + 1e-9)) if hi > lo else 0.5

        # 量能：近5日均量 / 近 slow_window 均量
        volume = self.am.volume
        self.vol_ratio = 1.0
        if len(volume) > self.slow_window:
            self.vol_ratio = float(np.mean(volume[-5:])) / (float(np.mean(volume[-self.slow_window:])) + 1e-9)

        self.bar_since_rebalance += 1
        rebalance = self.bar_since_rebalance >= self.fast_window

        if self.pos == 0:
            # 低价 + 放量启动
            if self.price_position < 0.25 and self.vol_ratio > self.volume_surge:
                self.buy(bar.close_price, self.fixed_size)
                self.bar_since_rebalance = 0
        elif self.pos > 0:
            if rebalance:
                self.sell(bar.close_price, abs(self.pos))
                self.bar_since_rebalance = 0

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass