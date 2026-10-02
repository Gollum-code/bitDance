from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyMlPredict(CtaTemplate):
    """机器学习方向预测族（在线滚动回归代理）。

    源模板：03 机器学习多因子 / 06 市值SVR / 30 LSTM / 43 无模型多因子 / 51 随机森林 / 98 SVM。
    说明：真实模型需要财务/高频数据与离线训练；此处以"在线滚动最小二乘"复刻其信号结构——
    用过去 N 日收益率序列做滚动线性回归，预测斜率方向作为多空信号。
    参数语义：fast_window=滚动回归窗口，slow_window=信号平滑窗口，signal_window=斜率阈值。
    """

    author = "bitDance"

    fast_window: int = 60
    slow_window: int = 10
    signal_window: float = 0.0
    fixed_size: int = 1

    slope_value: float = 0.0
    predicted: float = 0.0

    parameters = ["fast_window", "slow_window", "signal_window", "fixed_size"]
    variables = ["slope_value", "predicted", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.fast_window * 2)

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
        if self.am.count < self.fast_window:
            return

        close = self.am.close[-self.fast_window:]
        x = np.arange(len(close), dtype=float)
        y = close.astype(float)
        # 最小二乘斜率
        xm = x.mean()
        ym = y.mean()
        slope = float(np.sum((x - xm) * (y - ym)) / (np.sum((x - xm) ** 2) + 1e-12))
        self.slope_value = slope

        # 斜率归一化到价格尺度，并做短期平滑
        price_scale = float(close.mean()) + 1e-12
        signal = slope * self.fast_window / price_scale
        self.predicted = signal

        threshold = float(self.signal_window)
        if self.pos == 0:
            if self.predicted > threshold:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.predicted < -threshold:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass