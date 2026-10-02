# strategyMap.py
#暂时实际上没有用

from vnpy_ctastrategy.strategies.atr_rsi_strategy import AtrRsiStrategy
from vnpy_ctastrategy.strategies.boll_channel_strategy import BollChannelStrategy
from vnpy_ctastrategy.strategies.double_ma_strategy import DoubleMaStrategy
from vnpy_ctastrategy.strategies.dual_thrust_strategy import DualThrustStrategy
from vnpy_ctastrategy.strategies.king_keltner_strategy import KingKeltnerStrategy
from vnpy_ctastrategy.strategies.multi_signal_strategy import MultiSignalStrategy
from vnpy_ctastrategy.strategies.multi_timeframe_strategy import MultiTimeframeStrategy
from vnpy_ctastrategy.strategies.test_strategy import TestStrategy
from vnpy_ctastrategy.strategies.turtle_signal_strategy import TurtleSignalStrategy


STRATEGY_MAP = {
    "AtrRsiStrategy": AtrRsiStrategy,
    "BollChannelStrategy": BollChannelStrategy,
    "DoubleMaStrategy": DoubleMaStrategy,
    "DualThrustStrategy": DualThrustStrategy,
    "KingKeltnerStrategy": KingKeltnerStrategy,
    "MultiSignalStrategy": MultiSignalStrategy,
    "MultiTimeframeStrategy": MultiTimeframeStrategy,
    "TestStrategy": TestStrategy,
    "TurtleSignalStrategy": TurtleSignalStrategy,
}



def get_strategy_params(strategy_class):
    """
    从策略类的 parameters 中提取用户可配置的参数
    返回: [{"name": "atr_length", "type": "int", "default": 22}, ...]
    """
    params = []

    # vnpy 策略类的 parameters 定义了可调参数名
    param_names = getattr(strategy_class, 'parameters', [])

    for name in param_names:
        # 从类属性获取默认值
        default_value = getattr(strategy_class, name, None)
        param_type = type(default_value).__name__ if default_value is not None else 'str'

        params.append({
            "name": name,
            "type": param_type,
            "default": default_value,
        })

    return params





# 2. 运行时动态加载
strategy_name = "AtrRsiStrategy"  # 从配置文件、GUI输入或命令行读取
strategy_class = STRATEGY_MAP.get(strategy_name)

if strategy_class:
    #engine.add_strategy(strategy_class, {})
    print("成功")
else:
    print(f"策略 {strategy_name} 未找到")

paras=get_strategy_params(strategy_class)
print(paras)