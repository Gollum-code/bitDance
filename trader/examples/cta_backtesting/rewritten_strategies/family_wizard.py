from __future__ import annotations

import numpy as np

from vnpy_ctastrategy import ArrayManager, BarData, CtaTemplate, OrderData, TradeData

from rewritten_strategies import _family_helpers as H


class FamilyWizard(CtaTemplate):
    """向导式多因子族（聚宽向导 33 份模板的参数化归并）。

    源模板（聚宽"向导/策略生成器"家族，共 33 份）：
      08 MACD单因子多头 / 16 投资学作业 / 24 自选策略1 / 26 向导式-1 / 28 收益策略 /
      31 低PB价值 / 32 测试策略1 / 34 成长策略 / 35 简单多因子 / 36 多因子改进 / 37 个股止损 /
      44 新手价值 / 47 次新小盘 / 53 小市值 / 56 爱神的箭 / 57 黄泽森 / 58 MACD金叉 /
      60 投资期末 / 61 成长精选 / 62 选股策略 / 63 向导式 / 64 银行股轮动 / 70 蓝筹&均线 /
      74 沪深300增强 / 75 财务因子 / 80 价值分析 / 84 投资策略说明 / 87 张燕兰 / 88 小白多因子 /
      90 MA均线金叉 / 94 PE和PB / 95 资金流 / 99 中信证券向导。

    说明：向导模板本体是"聚宽财务/行情筛选 + 定期调仓"的框架，vn.py 日线回测没有
    财务字段与指数成分接口，因此改写为一个共享的参数化因子框架：价格形态因子
    （动量、乖离、相对强度）合成打分，加上可选的止损/止盈与调仓频率。
    原 33 份各自的差异（财务筛选方向、排序升降序、最大持仓）由参数 direction/sort_dir
    来区分，从根本上消除"33 份复制同一段代码"。
    参数语义：fast_window=动量窗口，slow_window=评分窗口，signal_window=入场阈值，
    atr_window=止盈/止损窗口，atr_mult=止损幅度，direction=多头(1)/空头(-1)风格，
    sort_dir=排序方向（保留，供跨标的扩展）。
    """

    author = "bitDance"

    fast_window: int = 5
    slow_window: int = 20
    signal_window: float = 0.0
    atr_window: int = 14
    atr_mult: float = 2.5
    fixed_size: int = 1
    direction: int = 1
    sort_dir: int = 1

    factor_score: float = 0.0
    stop_price: float = 0.0

    parameters = [
        "fast_window", "slow_window", "signal_window", "atr_window",
        "atr_mult", "fixed_size", "direction", "sort_dir",
    ]
    variables = ["factor_score", "stop_price", "pos"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am: ArrayManager = ArrayManager(self.slow_window * 3)
        self.direction = int(self.direction)

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

        # 多因子打分：动量 + 乖离 + 相对强度（合成分数，[-1,1] 归一化）
        mom = float(close[-1] / close[-self.slow_window] - 1.0)
        bias = H.bias_percent(close, self.fast_window) / 100.0
        short_ma = H.sma(close, self.fast_window)
        long_ma = H.sma(close, self.slow_window)
        rel = float((short_ma - long_ma) / (long_ma + 1e-9))

        raw = (mom + bias + rel) / 3.0
        # 分数被 direction 决定方向
        self.factor_score = self.direction * raw

        threshold = float(self.signal_window)
        if self.pos == 0:
            if self.factor_score > threshold:
                self.buy(bar.close_price, self.fixed_size)
        elif self.pos > 0:
            # 止盈/止损：跌破持仓最高价一定幅度平仓
            atr = H.atr(self.am.high, self.am.low, self.am.close, self.atr_window)
            if np.isnan(atr):
                atr = bar.close_price * 0.02
            self.stop_price = bar.close_price - self.atr_mult * atr
            if self.factor_score < -threshold or bar.close_price <= self.stop_price:
                self.sell(bar.close_price, abs(self.pos))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        pass

    def on_order(self, order: OrderData) -> None:
        pass