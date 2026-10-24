<script setup lang="ts">
import { computed } from 'vue'
import type { MonteCarloResult, MonthlyReturn, RiskGate, RiskMetrics } from '../../services/analytics'

const props = defineProps<{
  riskMetrics?: RiskMetrics
  monthlyReturns?: MonthlyReturn[]
  riskGate?: RiskGate
  monteCarlo?: MonteCarloResult
}>()

const rows = computed(() => {
  const m = props.riskMetrics
  if (!m) return []
  return [
    { label: '夏普比率', value: fmt(m.sharpe_ratio, 2), hint: '(年化收益-无风险利率)/年化波动' },
    { label: '索提诺比率', value: fmt(m.sortino_ratio, 2), hint: '分母仅用下行波动，不惩罚上涨' },
    { label: 'Calmar 比率', value: fmt(m.calmar_ratio, 2), hint: '年化收益/最大回撤' },
    { label: '年化波动率', value: pct(m.annual_volatility_pct), hint: '日波动×√252' },
    { label: '最大回撤', value: pct(m.max_drawdown_pct), hint: '峰值到谷值的最大跌幅' },
    { label: '回撤持续天数', value: int(m.max_drawdown_duration_days), hint: '从峰值到谷值的交易日数' },
    { label: '溃疡指数', value: pct(m.ulcer_index_pct), hint: '回撤平方均值开方，惩罚长期深回撤' },
    { label: 'VaR(95%)', value: pct(m.var_95_pct), hint: '历史模拟法，95%概率下单日最大亏损' },
    { label: 'CVaR(95%)', value: pct(m.cvar_95_pct), hint: '尾部平均亏损，比 VaR 更保守' },
    { label: '日胜率', value: pct(m.daily_win_rate * 100), hint: '盈利天数占总样本天数比例' },
    { label: '盈亏因子', value: fmtNull(m.profit_factor_daily, 2), hint: '日盈利总和/日亏损总和' },
    { label: '偏度', value: fmt(m.skew, 2), hint: '负值=左尾厚，极端亏损概率更高' },
    { label: '超额峰度', value: fmt(m.excess_kurtosis, 2), hint: '正值=尖峰厚尾，正态分布为 0' },
    {
      label: '有效交易天数',
      value: `${int(m.active_days ?? 0)}/${int(m.samples)}`,
      hint: '有盈亏的天数占比过低时比率不具统计意义',
    },
  ]
})

const monthlyRows = computed(() => (props.monthlyReturns ?? []).slice(-24))

const gate = computed(() => props.riskGate)

const mc = computed<MonteCarloResult | undefined>(() => {
  const m = props.monteCarlo
  return m && m.ok ? m : undefined
})

/** 置信区间行：左=点估计，右=95% 区间 */
const mcRows = computed(() => {
  const m = mc.value
  if (!m) return []
  const s = m.sample
  return [
    {
      label: '夏普比率',
      point: fmt(s?.sharpe, 2),
      lo: fmt(m.sharpe?.p05, 2),
      hi: fmt(m.sharpe?.p95, 2),
      hint: '区间跨越 0 说明无法排除无超额收益',
    },
    {
      label: '累计收益 %',
      point: fmt(s?.total_return_pct, 2),
      lo: fmt(m.total_return?.p05, 2),
      hi: fmt(m.total_return?.p95, 2),
      hint: '同样策略再跑一次，95% 概率落在此区间',
    },
    {
      label: '年化收益 %',
      point: fmt(s?.annual_return_pct, 2),
      lo: fmt(m.annual_return?.p05, 2),
      hi: fmt(m.annual_return?.p95, 2),
      hint: 'block bootstrap 重采样的年化分布',
    },
    {
      label: '最大回撤 %',
      point: fmt(s?.max_drawdown_pct, 2),
      lo: fmt(m.max_drawdown?.p05, 2),
      hi: fmt(m.max_drawdown?.p95, 2),
      hint: `95% 分位回撤 ${fmt(m.drawdown_p95, 2)}%——按此做风险预算更稳健`,
    },
  ]
})

function fmt(v: unknown, digits = 2): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  return v.toFixed(digits)
}

function fmtNull(v: number | null | undefined, digits = 2): string {
  return v == null ? '—' : v.toFixed(digits)
}

function pct(v: unknown): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  return `${v.toFixed(2)}%`
}

function int(v: unknown): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  return String(Math.round(v))
}

function monthColor(v: number): string {
  if (v > 0) return '#f5222d'
  if (v < 0) return '#16a34a'
  return '#8b98a9'
}
</script>

<template>
  <section v-if="riskMetrics" class="risk-panel">
    <header class="risk-head">
      <h3>风险与绩效深化</h3>
      <span v-if="riskMetrics.degenerate" class="risk-badge warn">指标退化</span>
      <span v-else-if="gate?.approved" class="risk-badge ok">风控通过</span>
      <span v-else-if="gate" class="risk-badge bad">风控否决</span>
    </header>

    <div v-if="riskMetrics.degenerate_reason" class="risk-degenerate">
      {{ riskMetrics.degenerate_reason }}
    </div>

    <div class="risk-grid">
      <div v-for="r in rows" :key="r.label" class="risk-cell" :title="r.hint">
        <span class="risk-label">{{ r.label }}</span>
        <span class="risk-value">{{ r.value }}</span>
      </div>
    </div>

    <div v-if="gate && gate.checks.length" class="risk-gate">
      <h4>风控硬规则检查（确定性判定，不含主观判断）</h4>
      <ul>
        <li v-for="c in gate.checks" :key="c.rule" :class="c.passed ? 'pass' : 'fail'">
          <span class="mark">{{ c.passed ? '✓' : '✕' }}</span>
          <span class="desc">{{ c.desc }}</span>
          <span class="nums">{{ c.value }} / {{ c.threshold }}</span>
        </li>
      </ul>
      <p v-if="gate.reasons.length" class="risk-reasons">否决原因：{{ gate.reasons.join('；') }}</p>
    </div>

    <div v-if="mc && mcRows.length" class="risk-mc">
      <h4>
        蒙特卡洛置信区间
        <span class="mc-meta">{{ mc.sims }} 次 block bootstrap · 块长 {{ mc.block }} 日 · {{ Math.round((mc.confidence ?? 0.95) * 100) }}%</span>
      </h4>
      <div class="mc-grid">
        <div v-for="r in mcRows" :key="r.label" class="mc-row" :title="r.hint">
          <span class="mc-label">{{ r.label }}</span>
          <span class="mc-point">{{ r.point }}</span>
          <span class="mc-ci">[{{ r.lo }}, {{ r.hi }}]</span>
        </div>
      </div>
      <div class="mc-probs">
        <span>收益为正概率 <b>{{ pct((mc.total_return?.prob_positive ?? 0) * 100) }}</b></span>
        <span>夏普为正概率 <b>{{ pct((mc.sharpe?.prob_positive ?? 0) * 100) }}</b></span>
      </div>
      <ul v-if="mc.interpretation?.length" class="mc-notes">
        <li v-for="(n, i) in mc.interpretation" :key="i">{{ n }}</li>
      </ul>
    </div>

    <div v-if="monthlyRows.length" class="risk-monthly">
      <h4>月度收益分布</h4>
      <div class="month-strip">
        <div v-for="m in monthlyRows" :key="m.month" class="month-item">
          <span class="month-label">{{ m.month.slice(2) }}</span>
          <span class="month-val" :style="{ color: monthColor(m.return_pct) }">
            {{ m.return_pct > 0 ? '+' : '' }}{{ m.return_pct.toFixed(2) }}%
          </span>
        </div>
      </div>
    </div>

    <p class="risk-note">
      口径：日频、年化 252、无风险利率 {{ pct((riskMetrics.risk_free_rate ?? 0.02) * 100) }}；
      日收益由权益曲线反推。风险比率在样本量不足或无有效波动时归零，不代表策略安全。
    </p>
  </section>
</template>

<style scoped>
.risk-panel {
  margin-top: 16px;
  padding: 14px 16px;
  border: 1px solid rgba(129, 156, 193, 0.22);
  border-radius: 10px;
  background: rgba(12, 20, 34, 0.55);
}

.risk-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.risk-head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #d7e4f7;
}

.risk-badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.risk-badge.ok {
  background: rgba(22, 163, 74, 0.16);
  color: #4ade80;
}

.risk-badge.bad {
  background: rgba(245, 34, 45, 0.16);
  color: #ff7875;
}

.risk-badge.warn {
  background: rgba(234, 179, 8, 0.16);
  color: #facc15;
}

.risk-degenerate {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-left: 3px solid #eab308;
  background: rgba(234, 179, 8, 0.08);
  color: #fde68a;
  font-size: 12px;
  line-height: 1.6;
}

.risk-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
}

.risk-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
}

.risk-label {
  font-size: 11px;
  color: #8b9bb4;
}

.risk-value {
  font-size: 15px;
  font-weight: 600;
  color: #e8f0fb;
  font-variant-numeric: tabular-nums;
}

.risk-gate {
  margin-top: 12px;
}

.risk-gate h4,
.risk-monthly h4 {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: #a9bcd6;
}

.risk-gate ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 4px;
}

.risk-gate li {
  display: grid;
  grid-template-columns: 18px 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 5px 8px;
  border-radius: 6px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.02);
}

.risk-gate li.pass .mark {
  color: #4ade80;
}

.risk-gate li.fail {
  background: rgba(245, 34, 45, 0.08);
}

.risk-gate li.fail .mark {
  color: #ff7875;
}

.risk-gate .desc {
  color: #c3d2e8;
}

.risk-gate .nums {
  color: #8b9bb4;
  font-variant-numeric: tabular-nums;
}

.risk-reasons {
  margin: 8px 0 0;
  font-size: 12px;
  color: #ffa39e;
}

.risk-monthly {
  margin-top: 12px;
}

.risk-mc {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed rgba(129, 156, 193, 0.18);
}

.risk-mc h4 {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: #a9bcd6;
}

.mc-meta {
  margin-left: 8px;
  font-weight: 400;
  color: #7f8ea3;
}

.mc-grid {
  display: grid;
  gap: 4px;
}

.mc-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 10px;
  align-items: center;
  padding: 5px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.02);
  font-size: 12px;
}

.mc-label {
  color: #c3d2e8;
}

.mc-point {
  color: #e8f0fb;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.mc-ci {
  color: #8b9bb4;
  font-variant-numeric: tabular-nums;
}

.mc-probs {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 8px;
  font-size: 12px;
  color: #8b9bb4;
}

.mc-probs b {
  color: #d7e4f7;
}

.mc-notes {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #8b9bb4;
  font-size: 11px;
  line-height: 1.7;
}

.month-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.month-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 52px;
  padding: 5px 6px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
}

.month-label {
  font-size: 10px;
  color: #7f8ea3;
}

.month-val {
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.risk-note {
  margin: 12px 0 0;
  font-size: 11px;
  line-height: 1.6;
  color: #7f8ea3;
}
</style>
