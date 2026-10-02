# CTA 日线回测 Demo

这是一个基于 `vnpy_ctastrategy` 的最小可运行日线回测示例。

## 文件

- `daily_ma_cross_strategy.py`：日线均线交叉策略
- `run_daily_backtest.py`：回测启动脚本

## 默认参数

- `vt_symbol=600031.SSE`
- `interval=DAILY`
- `fast_window=5`
- `slow_window=10`
- `fixed_size=1`

## 运行

在项目根目录下执行：

```powershell
python .\ai\tests\cta_backtesting\run_daily_backtest.py
```

切换到另一个合约：

```powershell
python .\ai\tests\cta_backtesting\run_daily_backtest.py --vt-symbol 600036.SSE
```

如果你想改参数：

```powershell
python .\ai\tests\cta_backtesting\run_daily_backtest.py --fast-window 3 --slow-window 8 --fixed-size 10
```

