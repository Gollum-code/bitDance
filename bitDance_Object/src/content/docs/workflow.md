# 画布工作流说明

## 策略构建三阶段

1. **信号生成**：输入行情与链上因子，生成标准化交易信号。
2. **风险约束**：限制仓位、集中度与风格暴露，控制回撤。
3. **执行路由**：根据流动性与滑点模型拆单执行。

## 推荐实践

- 先从模板策略复制，再做局部参数改造。
- 每次只改一组参数，方便定位收益变化来源。
- 回测后记录“收益/回撤/胜率/换手率”四个核心指标。

## 示例配置

```ts
const strategy = {
  signal: { model: 'momentum', lookback: 21 },
  risk: { maxDrawdown: 0.12, leverage: 1.2 },
  execution: { router: 'smart-split', slippageBps: 8 },
}
```
