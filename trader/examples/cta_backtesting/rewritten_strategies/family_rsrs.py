from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyRsrs(CtaTemplate):
    """RSRS 阻力支撑相对强度择时族。

    源模板：05 兄台且慢 / 27 RSRS择时30分钟 / 69 RSRS指标择时 / 77 RSRS优化 / 93 RSRS大盘择时。
    逻辑：以 fast_window 高低点为样本线性回归，取斜率 beta 与决定系数 r2，
    计算标准化 RSRS 值；上穿买入阈值开多，下穿卖出阈值平多。
    参数语义：fast_window=回归窗口，slow_window=RSRS 标准差平滑窗口，
    signal_window=买入阈值，atr_window=卖出阈值。
    """

    author = "bitDance"

    fast_window: int = 18
    slow_window: int = 60
    signal_window: int = 0.7
    atr_window: int = -0.7
    fixed_size: int = 1

    rsrs_value: float = 0.0
    rsrs_beta: float = 0.0
    rsrs_r2: float = 0.0

    parameters = ["fast_window", "slow_window", "signal_window", "atr_window", "fixed_size"]
    variables = ["rsrs_value", "rsrs_beta", "rsrs_r2", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.fast_window * 6)
        self.beta_cache: list[float] = []
        self.buy_threshold: float = float(self.signal_window)
        self.sell_threshold: float = float(self.atr_window)

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
        if self.am.count < self.fast_window + 2:
            return

        high = self.am.high
        low = self.am.low

        beta, r2 = H.rsrs_slope(high, low, self.fast_window)
        if np.isnan(beta):
            return

        self.beta_cache.append(beta * r2)
        if len(self.beta_cache) > self.slow_window:
            self.beta_cache = self.beta_cache[-self.slow_window:]

        if len(self.beta_cache) < self.slow_window:
            self.rsrs_value = 0.0
        else:
            arr = np.array(self.beta_cache)
            mu = float(np.mean(arr))
            sd = float(np.std(arr))
            self.rsrs_value = float((arr[-1] - mu) / sd) if sd > 1e-12 else 0.0

        self.rsrs_beta = float(beta)
        self.rsrs_r2 = float(r2)

        if self.pos == 0:
            if self.rsrs_value > self.buy_threshold:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.rsrs_value < self.sell_threshold:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass