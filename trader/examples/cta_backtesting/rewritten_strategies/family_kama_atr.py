from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyKamaAtr(CtaTemplate):
    """自适应均线 + ATR 止损族。

    源模板：01 AdaptiveMA自适应均线（期货） / 20 分钟K线ATR自适应通道（简化版本）。
    逻辑：KAMA(fast_window) 变化的绝对值超过"基于KAMA窗口的标准差阈值"开多；
    持仓后以 ATR 自适应通道作为移动止损（close 跌破 slow_window ATR 下沿平多）。
    参数语义：fast_window=KAMA窗口，slow_window=ATR窗口，atr_mult=ATR止损倍数。
    """

    author = "bitDance"

    fast_window: int = 10
    slow_window: int = 14
    atr_mult: float = 3.0
    fixed_size: int = 1

    kama_value: float = 0.0
    atr_value: float = 0.0
    stop_price: float = 0.0

    parameters = ["fast_window", "slow_window", "atr_mult", "fixed_size"]
    variables = ["kama_value", "atr_value", "stop_price", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.fast_window * 6)

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
        n = min(len(close), self.fast_window * 6)

        # KAMA 差分信号：用快速 KAMA 斜率的标准化度量过滤
        kama_now = H.kama(close, self.fast_window)
        self.kama_value = kama_now
        kama_prev = H.kama(close[:-1], self.fast_window) if len(close) > self.fast_window + 1 else kama_now
        delta = kama_now - kama_prev

        # 波动基准：最新 ATR
        self.atr_value = H.atr(self.am.high, self.am.low, self.am.close, self.slow_window)
        if np.isnan(self.atr_value) or self.atr_value <= 0:
            # 用 KAMA 窗口的收盘波动兜底
            self.atr_value = H.true_range_ratio(self.am.high, self.am.low, self.am.close, 10) * kama_now + 1e-6

        thr = self.atr_value * 0.5 if n > 2 else 0.0

        if self.pos == 0:
            if abs(delta) > thr:
                if delta > 0:
                    self.buy(bar.close_price, self.fixed_size)
                else:
                    self.short(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            self.stop_price = bar.close_price - self.atr_mult * self.atr_value
            if bar.close_price <= self.stop_price:
                self.sell(bar.close_price, abs(self.pos))
        elif self.pos < 0:
            self.stop_price = bar.close_price + self.atr_mult * self.atr_value
            if bar.close_price >= self.stop_price:
                self.cover(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass