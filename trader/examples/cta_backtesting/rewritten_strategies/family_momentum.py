from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyMomentum(CtaTemplate):
    """商品期货动量/追板突破族。

    源模板：04 商品期货动量效应 / 17 截面动量（单标近似） / 10 追三板（放量突破）。
    逻辑：past_window 日动量（当前价/prev 价-1）超过阈值开多，动量转负或跌破
    短期均线平多；追板风格要求放量（volume 突增）。
    参数语义：fast_window=短期均线窗口，slow_window=动量窗口，signal_window=动量阈值(千分比)。
    """

    author = "bitDance"

    fast_window: int = 5
    slow_window: int = 20
    signal_window: float = 0.01
    fixed_size: int = 1

    momentum_value: float = 0.0
    ma_short: float = 0.0

    parameters = ["fast_window", "slow_window", "signal_window", "fixed_size"]
    variables = ["momentum_value", "ma_short", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.slow_window * 3)
        self.momentum_threshold: float = float(self.signal_window)

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
        if len(close) < self.slow_window + 1:
            return

        self.momentum_value = float(close[-1] / close[-self.slow_window - 1] - 1.0)
        self.ma_short = H.sma(close, self.fast_window)

        # 放量确认（追板风格）
        volume = self.am.volume
        vol_surge = len(volume) >= 3 and float(np.mean(volume[-3:])) > float(np.mean(volume[-6:-3]))

        if self.pos == 0:
            if self.momentum_value > self.momentum_threshold and vol_surge:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.momentum_value < 0.0 or bar.close_price < self.ma_short:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass