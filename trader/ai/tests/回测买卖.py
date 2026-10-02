from datetime import datetime
from vnpy_ctastrategy.backtesting import BacktestingEngine
from vnpy_ctastrategy.template import CtaTemplate


class SimpleStrategy(CtaTemplate):
    """
    简化策略，测试是否调用生效
    """
    author = "Test"

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

    def on_init(self):
        """初始化策略"""
        self.write_log("策略初始化")

    def on_bar(self, bar):
        """"""
        # 简单策略：每天买入
        if not self.pos:
            self.buy(bar.close_price, 1)
        else:
            self.sell(bar.close_price, 1)


# 测试简化策略
engine = BacktestingEngine()
engine.set_parameters(
    vt_symbol="600031.SSE",
    interval="d",
    start=datetime(2025, 1, 2),
    end=datetime(2025, 4, 9),
    rate=0.03 / 100,
    slippage=0.01,
    size=100,
    pricetick=0.01,
    capital=1_000_000,
)
engine.add_strategy(SimpleStrategy, {})

engine.load_data()
engine.run_backtesting()
df = engine.calculate_result()
engine.calculate_statistics()