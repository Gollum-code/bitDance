from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyKdj(CtaTemplate):
    """KD/KDJ 随机指标族。

    源模板：29 KD指标量化交易 / 40 kdj配合accer过滤 / 48 再测一支 / 91 Stoch（KDJ）大盘择时。
    逻辑：K 上穿 D 且不超买开多，K 下穿 D 或超买回落平多；
    accer 过滤：仅当量能加速度为正时才允许开多。
    参数语义：fast_window=N，signal_window=M1，atr_window=M2，atr_mult=超买阈值(80)。
    """

    author = "bitDance"

    fast_window: int = 9
    signal_window: int = 3
    atr_window: int = 3
    atr_mult: float = 80.0
    fixed_size: int = 1

    k_value: float = 0.0
    d_value: float = 0.0

    parameters = ["fast_window", "signal_window", "atr_window", "atr_mult", "fixed_size"]
    variables = ["k_value", "d_value", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.fast_window * 8)
        self.overbought: float = float(self.atr_mult)
        self.prev_k: float = 0.0
        self.prev_d: float = 0.0

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

        k, d = H.kdj_stoch(
            self.am.high, self.am.low, self.am.close,
            self.fast_window, int(self.signal_window), int(self.atr_window),
        )
        self.k_value = k
        self.d_value = d

        # 量能加速度：近3日成交量相对前3日是否放大
        vol = self.am.volume
        accer = 1.0
        if len(vol) >= 6:
            accer = float(np.sum(vol[-3:])) / (float(np.sum(vol[-6:-3])) + 1e-9)

        if self.pos == 0:
            if k > d and self.prev_k <= self.prev_d and k < self.overbought and accer > 0.8:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if k < d and self.prev_k >= self.prev_d:
                self.sell(bar.close_price, abs(self.pos))

        self.prev_k = k
        self.prev_d = d
        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass