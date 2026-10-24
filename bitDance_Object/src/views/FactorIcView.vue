<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import VChart from 'vue-echarts'
import { Sigma, Play, Loader2, Plus, Trash2 } from 'lucide-vue-next'
import { getFactorUniverse, runFactorIc, type FactorIcPayload } from '../services/analytics'
import { defaultChartEndDate } from '../services/market'

/** A 股配色：涨红跌绿（与项目其余图表一致） */
function priceColor(v: number | undefined | null): string {
  return (v ?? 0) >= 0 ? '#f87171' : '#4ade80'
}

const symbols = ref<string[]>([])
const factor = ref('momentum')
const horizon = ref(20)
const lookback = ref(120)
const endDate = ref(defaultChartEndDate())
const newSymbol = ref('600030.SSE')

const loading = ref(false)
const err = ref('')
const data = ref<FactorIcPayload | null>(null)

const FACTORS = [
  { value: 'momentum', label: '动量（20 日涨幅）', dir: '越高越好' },
  { value: 'trend', label: '中期趋势（价格/MA60）', dir: '越高越好' },
  { value: 'ma_bias', label: '乖离率（价格/MA20）', dir: '越低越好' },
  { value: 'volatility', label: '年化波动率', dir: '越低越好' },
  { value: 'vol_ratio', label: '量能放大（5日/20日均量）', dir: '越高越好' },
  { value: 'amihud', label: '非流动性冲击（Amihud）', dir: '越低越好' },
  { value: 'drawdown_from_high', label: '距 60 日高点回撤', dir: '越低越好' },
]

const currentFactor = computed(() => FACTORS.find((f) => f.value === factor.value))

const verdictColor = computed(() => {
  const v = data.value?.ic?.verdict
  if (v === 'effective') return '#4ade80'
  if (v === 'weak') return '#f0b429'
  if (v === 'ineffective') return '#f87171'
  return '#8b9bb4'
})

const icChart = computed<EChartsOption>(() => {
  const series = data.value?.ic_series ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 56, right: 24, top: 24, bottom: 40 },
    xAxis: {
      type: 'category',
      data: series.map((_, i) => `T-${series.length - i - 1}`),
      axisLabel: { color: '#7f8ea3', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      name: 'RankIC',
      nameTextStyle: { color: '#7f8ea3' },
      axisLabel: { color: '#7f8ea3', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,.06)' } },
    },
    series: [
      {
        type: 'line',
        data: series,
        smooth: false,
        showSymbol: true,
        symbolSize: 4,
        lineStyle: { color: '#5aa9ff', width: 1.6 },
        itemStyle: {
          color: (p: { value?: unknown }) => priceColor(Number(p.value ?? 0)),
        },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{ yAxis: 0 }],
          lineStyle: { color: 'rgba(255,255,255,.2)' },
        },
      },
    ],
  }
})

const quantileChart = computed<EChartsOption>(() => {
  const rets = data.value?.quantile?.group_returns_pct ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 56, right: 24, top: 24, bottom: 40 },
    xAxis: {
      type: 'category',
      data: rets.map((_, i) => `Q${i + 1}`),
      axisLabel: { color: '#7f8ea3', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      name: '未来收益 %',
      nameTextStyle: { color: '#7f8ea3' },
      axisLabel: { color: '#7f8ea3', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,.06)' } },
    },
    series: [
      {
        type: 'bar',
        data: rets,
        barMaxWidth: 46,
        itemStyle: {
          color: (p: { value?: unknown }) => priceColor(Number(p.value ?? 0)),
        },
      },
    ],
  }
})

function addSymbol() {
  const v = newSymbol.value.trim()
  if (!v || symbols.value.includes(v)) return
  if (symbols.value.length >= 20) {
    err.value = '最多 20 个标的'
    return
  }
  symbols.value.push(v)
  newSymbol.value = ''
}

function removeSymbol(i: number) {
  symbols.value.splice(i, 1)
}

async function run() {
  if (symbols.value.length < 5) {
    err.value = '至少需要 5 个标的做横截面'
    return
  }
  loading.value = true
  err.value = ''
  try {
    data.value = await runFactorIc({
      vt_symbols: symbols.value,
      factor: factor.value,
      horizon: horizon.value,
      lookback_days: lookback.value,
      end_date: endDate.value,
    })
  } catch (e) {
    err.value = e instanceof Error ? e.message : '因子分析失败'
    data.value = null
  } finally {
    loading.value = false
  }
}

function fmt(v: number | null | undefined, d = 4): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return Number(v).toFixed(d)
}

onMounted(async () => {
  try {
    const res = await getFactorUniverse(20)
    symbols.value = res.symbols
  } catch {
    symbols.value = ['600519.SSE', '000001.SZSE', '600036.SSE', '601318.SSE', '000858.SZSE']
  }
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title"><Sigma class="ic" /> 因子有效性分析（IC / IR）</h1>
        <p class="lead">
          选股器的因子权重此前是拍脑袋定的。这里用 IC / RankIC / IC_IR / 分组收益
          检验每个因子在本市场样本里到底有没有预测力——IC_IR 绝对值 &gt; 0.3 才算稳定有效。
        </p>
      </div>
    </header>

    <section class="panel">
      <div class="controls">
        <label class="fld">
          <span>因子</span>
          <select v-model="factor">
            <option v-for="f in FACTORS" :key="f.value" :value="f.value">{{ f.label }}</option>
          </select>
        </label>
        <label class="fld">
          <span>预测周期 horizon（日）</span>
          <input v-model.number="horizon" type="number" min="1" max="120" />
        </label>
        <label class="fld">
          <span>回看天数</span>
          <input v-model.number="lookback" type="number" min="40" max="400" step="10" />
        </label>
        <label class="fld">
          <span>截止日期</span>
          <input v-model="endDate" type="date" />
        </label>
        <button class="btn primary" :disabled="loading" @click="run">
          <Loader2 v-if="loading" class="ic spin" />
          <Play v-else class="ic" />
          {{ loading ? '计算中...' : '开始计算' }}
        </button>
      </div>
      <p class="hint">
        方向：{{ currentFactor?.dir }} · 需要足够标的数（建议 10+）与足够期数才能得到有意义的 IC_IR。
        计算会逐个拉取日线，首次可能较慢。
      </p>

      <div class="symbol-editor">
        <span class="se-label">样本标的（{{ symbols.length }}）</span>
        <input v-model="newSymbol" placeholder="600030.SSE" @keyup.enter="addSymbol" />
        <button class="btn tiny" @click="addSymbol"><Plus class="ic" /> 添加</button>
        <div class="chips">
          <span v-for="(s, i) in symbols" :key="s" class="chip">
            {{ s }}
            <button class="rm" @click="removeSymbol(i)"><Trash2 class="ic-sm" /></button>
          </span>
        </div>
      </div>
      <p v-if="err" class="err">{{ err }}</p>
    </section>

    <template v-if="data?.success">
      <section class="panel">
        <div class="summary">
          <div class="metric">
            <span class="metric-label">RankIC 均值</span>
            <strong class="metric-value" :style="{ color: verdictColor }">{{ fmt(data.ic.ic_mean) }}</strong>
          </div>
          <div class="metric">
            <span class="metric-label">IC 标准差</span>
            <strong class="metric-value">{{ fmt(data.ic.ic_std) }}</strong>
          </div>
          <div class="metric">
            <span class="metric-label">IC_IR</span>
            <strong class="metric-value" :style="{ color: verdictColor }">{{ fmt(data.ic.ic_ir) }}</strong>
            <span class="metric-hint">|IC_IR| &gt; 0.3 视为稳定</span>
          </div>
          <div class="metric">
            <span class="metric-label">t 值</span>
            <strong class="metric-value">{{ fmt(data.ic.t_stat, 2) }}</strong>
            <span class="metric-hint">|t| &gt; 2 显著</span>
          </div>
          <div class="metric">
            <span class="metric-label">IC 为正比例</span>
            <strong class="metric-value">{{ data.ic.positive_ratio == null ? '—' : `${Math.round(data.ic.positive_ratio * 100)}%` }}</strong>
          </div>
          <div class="metric">
            <span class="metric-label">结论</span>
            <strong class="metric-value" :style="{ color: verdictColor }">{{ data.ic.verdict_label }}</strong>
            <span class="metric-hint">{{ data.periods }} 期 · {{ data.symbols.length }} 标的</span>
          </div>
        </div>
        <p class="hint">{{ data.message }}</p>
      </section>

      <section class="panel half">
        <h2 class="h2">RankIC 时序</h2>
        <div class="chart-wrap">
          <v-chart class="chart" :option="icChart" autoresize />
        </div>
      </section>

      <section v-if="data.quantile?.ok" class="panel half">
        <h2 class="h2">
          分组未来收益
          <span class="h2-meta">多空价差 {{ fmt(data.quantile.long_short_spread_pct, 2) }}% · 单调性 {{ fmt(data.quantile.monotonicity, 2) }}</span>
        </h2>
        <div class="chart-wrap">
          <v-chart class="chart" :option="quantileChart" autoresize />
        </div>
        <p class="hint">
          Q1 为因子值最低组、Q{{ data.quantile.quantiles }} 为最高组。
          单调性接近 ±1 说明方向稳定，接近 0 说明分组没有区分度。
        </p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; padding: 5.5rem 1.2rem 4rem; max-width: 1100px; margin: 0 auto; }
.head { margin-bottom: 1.2rem; }
.title { display: flex; align-items: center; gap: .5rem; margin: 0; font-size: 1.45rem; color: var(--bq-text); }
.lead { margin: .4rem 0 0; color: var(--bq-muted); font-size: .88rem; line-height: 1.7; max-width: 880px; }
.panel { margin-bottom: 1rem; padding: 1rem; border-radius: .9rem; background: var(--bq-bg-elevated); border: 1px solid rgba(255,255,255,.06); }
.panel.half { margin-bottom: 1rem; }
.controls { display: flex; flex-wrap: wrap; gap: .6rem; align-items: end; }
.fld { display: grid; gap: .25rem; font-size: .78rem; color: var(--bq-muted); }
.fld input, .fld select { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .45rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); }
.fld input { width: 150px; }
.btn { display: inline-flex; align-items: center; gap: .35rem; border: 0; border-radius: 999px; padding: .55rem 1rem; font-size: .85rem; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; }
.btn.tiny { background: rgba(255,255,255,.08); color: var(--bq-text); padding: .4rem .7rem; font-size: .76rem; }
.btn:disabled { opacity: .55; cursor: not-allowed; }
.ic { width: 1rem; height: 1rem; }
.ic-sm { width: .8rem; height: .8rem; }
.spin { animation: sp 1s linear infinite; }
@keyframes sp { to { transform: rotate(360deg); } }
.err { margin: .6rem 0 0; color: #f87171; font-size: .82rem; }
.hint { margin: .6rem 0 0; color: var(--bq-muted); font-size: .76rem; line-height: 1.6; }
.h2 { margin: 0 0 .7rem; font-size: .95rem; color: var(--bq-text); }
.h2-meta { margin-left: .5rem; font-weight: 400; color: var(--bq-muted); font-size: .78rem; }
.symbol-editor { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; margin-top: .9rem; padding-top: .9rem; border-top: 1px dashed rgba(255,255,255,.08); }
.se-label { font-size: .78rem; color: var(--bq-muted); }
.symbol-editor input { width: 130px; border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .4rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); }
.chips { display: flex; flex-wrap: wrap; gap: .35rem; }
.chip { display: inline-flex; align-items: center; gap: .3rem; padding: .25rem .5rem; border-radius: 999px; background: rgba(90,169,255,.12); color: #bcd6f7; font-size: .74rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.chip .rm { border: 0; background: transparent; color: #f87171; cursor: pointer; display: inline-flex; padding: 0; }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .7rem; }
.metric { display: flex; flex-direction: column; gap: .2rem; padding: .7rem .8rem; border-radius: .6rem; background: rgba(255,255,255,.03); }
.metric-label { font-size: .72rem; color: #8b9bb4; }
.metric-value { font-size: 1.25rem; color: var(--bq-text); font-variant-numeric: tabular-nums; }
.metric-hint { font-size: .68rem; color: #6f7f94; }
.chart-wrap { height: 300px; }
.chart { width: 100%; height: 100%; }
</style>
