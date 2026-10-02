from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilySmartMoney(CtaTemplate):
    """聪明钱/资金流跟踪族（量价因子代理）。

    源模板：38 跟踪聪明钱（VWAP 权重因子） / 73 北向资金买入A股（proxy）。
    说明：原模板用主力净流入/北向持仓等场外数据，vn.py 日线用"涨跌幅÷√成交量"
    构造聪明钱因子（模板 38 的核心思路）：放量上涨定义为聪明钱进场。
    参数语义：fast_window=因子窗口，slow_window=量能均值窗口，
    signal_window=因子阈值，atr_window=持仓观察窗口。
    """

    author = "bitDance"

    fast_window: int = 10
    slow_window: int = 20
    signal_window: float = 0.001
    atr_window: int = 30
    fixed_size: int = 1

    smart_factor: float = 0.0
    volume_mean: float = 0.0

    parameters = ["fast_window", "slow_window", "signal_window", "atr_window", "fixed_size"]
    variables = ["smart_factor", "volume_mean", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(max(self.slow_window, self.atr_window) * 3)
        self.factor_threshold: float = float(self.signal_window)

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
        volume = self.am.volume
        ret = np.zeros(len(close))
        if len(close) >= 2:
            ret[1:] = np.diff(close) / close[:-1] * 100.0  # 百分率涨跌幅

        smart = np.zeros(len(close))
        vol_safe = np.where(volume > 0, volume, 1e-9)
        smart = ret / np.sqrt(vol_safe)

        self.smart_factor = float(np.mean(smart[-self.fast_window:]))
        self.volume_mean = float(np.mean(volume[-self.slow_window:]))

        if self.pos == 0:
            if self.smart_factor > self.factor_threshold and bar.close_price > H.sma(close, self.fast_window):
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            if self.smart_factor < 0.0:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass