# 策略与回测

## 1. 策略从哪来

项目把聚宽社区 **99 份策略模板**去重改写为 **23 个 vn.py `CtaTemplate` 策略族**：

- `trader/examples/cta_backtesting/rewritten_strategies/family_*.py` —— 23 个族策略
- `_family_helpers.py` —— 族策略公共指标库（`sma/ema/zscore/rsrs/kdj/atr/kama` 等）
- `manifest.csv` —— 99 份模板 → 族策略类 + 默认参数的映射表

> 原始 33 份"向导式"模板是同一套聚宽向导框架的参数化副本，改写时归并为
> `FamilyWizard` 一个族；其余 66 份按策略逻辑（均线/MACD/RSRS/布林/海龟/机器学习等）
> 归类为各自独立的族策略，避免"复制粘贴同一段模板"。

## 2. 运行一次回测

前置：目标标的日线已在本地库（见「快速开始」第 3 步）。

1. 进入「我的策略」（`/strategies`）
2. 选择策略（按 `strategy_id` + 族名），填写标的 `vt_symbol`（如 `600519.SSE`）与时间区间
3. 可选覆盖族默认参数（`fast_window` / `slow_window` / `fixed_size` 等）
4. 点击运行，得到统计指标 + 权益曲线 + 交易明细

命令行方式（trader 服务 8000）：

```bash
# 全部默认参数
curl "http://localhost:8000/strategy/01?vt_symbol=600519.SSE&start=2024-01-01&end=2025-12-31"

# 覆盖参数
curl "http://localhost:8000/strategy/01?vt_symbol=600519.SSE&start=2024-01-01&end=2025-12-31&fast_window=10&fixed_size=5"
```

## 3. 回测报告与 AI 分析

回测成功后，在右下角 **bitDance AI** 面板点击「生成回测报告」：

- 自动汇总参数、统计指标、权益曲线与交易质量
- 由 Kimi 生成 markdown 报告，保存在「回测历史报告」（`/report-history`）
- 支持导出 **PDF**，支持勾选多份报告做 **指标对比**（总收益/年化/回撤/夏普/胜率/成交笔数并排）

## 4. 实盘注意

回测结果仅供研究。实盘前请完成：

- 手续费 / 滑点建模
- 参数稳健性检验
- 风控规则验证（仓位、止损、风控阈值）