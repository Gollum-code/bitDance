<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import VChart from 'vue-echarts'
import { Briefcase, Play, Loader2, Plus, Trash2 } from 'lucide-vue-next'
import { listStrategies, type StrategyListItem } from '../services/backtest'
import { runPortfolio, type PortfolioPayload } from '../services/analytics'
import { defaultChartEndDate, defaultChartStartDate } from '../services/market'

const strategies = ref<StrategyListItem[]>([])
const sid = ref('01')
const symbols = ref<string[]>(['600519.SSE', '000001.SZSE'])
const weights = ref<number[]>([0.5, 0.5])
const start = ref(defaultChartStartDate(2))
const end = ref(defaultChartEndDate())
const capital = ref(100000)

const loading = ref(false)
const err = ref('')
const data = ref<PortfolioPayload | null>(null)

function addSymbol() {
  if (symbols.value.length >= 10) return
  symbols.value.push('600036.SSE')
  weights.value.push(0)
  rebalanceWeights()
}

function removeSymbol(i: number) {
  symbols.value.splice(i, 1)
  weights.value.splice(i, 1)
  rebalanceWeights()
}

function setWeight(i: number, v: number) {
  weights.value[i] = v
}

function rebalanceWeights() {
  const n = symbols.value.length
  weights.value = new Array(n).fill(1 / n)
}

function weightSum() {
  return weights.value.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0)
}

const chartOption = computed<EChartsOption>(() => {
  const dates = data.value?.dates ?? []
  const nav = data.value?.nav ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = params as { axisValue?: string; data?: unknown }[]
        if (!p.length) return ''
        const d = p[0].axisValue ?? ''
        const v = Number(p[0].data ?? 1)
        return `${d}<br/>净值：${v.toFixed(4)}<br/>累计：${((v - 1) * 100).toFixed(2)}%`
      },
    },
    grid: { left: 64, right: 24, top: 32, bottom: 48 },
    xAxis: { type: 'category', data: dates, axisLabel: { color: '#7f8ea3', fontSize: 10 } },
    yAxis: {
      type: 'value',
      name: '组合净值',
      nameTextStyle: { color: '#7f8ea3' },
      axisLabel: { color: '#7f8ea3', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,.06)' } },
    },
    series: [
      {
        name: '组合净值',
        type: 'line',
        data: nav,
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#f0b429', width: 2 },
        areaStyle: { color: 'rgba(240, 180, 41, 0.12)' },
      },
    ],
  }
})

const STAT_ROWS: { key: string; label: string; fmt: (v: unknown) => string }[] = [
  { key: 'total_return', label: '组合总收益 %', fmt: (v) => fmtNum(v, 2) },
  { key: 'annual_return', label: '年化收益 %', fmt: (v) => fmtNum(v, 2) },
  { key: 'max_drawdown', label: '最大回撤 %', fmt: (v) => fmtNum(v, 2) },
  { key: 'sharpe_ratio', label: '夏普比率', fmt: (v) => fmtNum(v, 2) },
  { key: 'total_trade_count', label: '总成交笔数', fmt: (v) => fmtNum(v, 0) },
]

function fmtNum(v: unknown, d = 2) {
  const n = typeof v === 'number' ? v : Number(v)
  if (v === undefined || v === null || Number.isNaN(n)) return '—'
  return n.toFixed(d)
}

function statValue(key: string): unknown {
  const s = data.value?.stats
  if (!s) return undefined
  return s[key as keyof typeof s]
}

async function run() {
  if (symbols.value.length < 2) {
    err.value = '组合至少需要 2 个标的'
    return
  }
  if (Math.abs(weightSum() - 1) > 0.02) {
    err.value = `权重之和需为 1，当前为 ${weightSum().toFixed(2)}`
    return
  }
  loading.value = true
  err.value = ''
  try {
    data.value = await runPortfolio({
      strategy_id: sid.value,
      vt_symbols: symbols.value.map((s) => s.trim()).filter(Boolean),
      weights: weights.value,
      start: start.value,
      end: end.value,
      capital: capital.value,
    })
  } catch (e) {
    err.value = e instanceof Error ? e.message : '组合回测失败'
    data.value = null
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    strategies.value = await listStrategies()
    if (strategies.value[0]) sid.value = strategies.value[0].strategy_id
  } catch (e) {
    err.value = e instanceof Error ? e.message : '策略清单加载失败'
  }
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title"><Briefcase class="ic" /> 组合回测</h1>
        <p class="lead">单个策略在多标的组合上等权/加权回测，输出组合净值、回撤与夏普</p>
      </div>
    </header>

    <section class="panel">
      <div class="controls-top">
        <label class="fld">
          <span>策略</span>
          <select v-model="sid">
            <option v-for="s in strategies" :key="s.strategy_id" :value="s.strategy_id">
              {{ s.strategy_id }} · {{ s.class_name ?? '' }}
            </option>
          </select>
        </label>
        <label class="fld">
          <span>开始</span>
          <input v-model="start" type="date" />
        </label>
        <label class="fld">
          <span>结束</span>
          <input v-model="end" type="date" />
        </label>
        <label class="fld">
          <span>初始资金</span>
          <input v-model.number="capital" type="number" min="10000" step="10000" />
        </label>
        <button class="btn primary" :disabled="loading" @click="run">
          <Loader2 v-if="loading" class="ic spin" />
          <Play v-else class="ic" />
          {{ loading ? '回测中…' : '运行组合回测' }}
        </button>
      </div>

      <div class="symbols">
        <div v-for="(s, i) in symbols" :key="i" class="sym-row">
          <input v-model="symbols[i]" class="mono" placeholder="600519.SSE" />
          <input
            v-model.number="weights[i]"
            class="w-input"
            type="number"
            min="0"
            max="1"
            step="0.05"
            placeholder="权重"
            @input="setWeight(i, weights[i])"
          />
          <span class="w-pct">{{ ((weights[i] ?? 0) * 100).toFixed(0) }}%</span>
          <button type="button" class="icon-btn danger" :disabled="symbols.length <= 2" @click="removeSymbol(i)">
            <Trash2 class="ic" />
          </button>
        </div>
        <div class="sym-actions">
          <button type="button" class="btn" :disabled="symbols.length >= 10" @click="addSymbol">
            <Plus class="ic" /> 添加标的
          </button>
          <button type="button" class="btn" @click="rebalanceWeights">等权重重置</button>
          <span class="w-sum">权重合计：{{ (weightSum() * 100).toFixed(0) }}%</span>
        </div>
      </div>
      <p v-if="err" class="err">{{ err }}</p>
      <p v-else-if="data" class="ok">{{ data.message }}</p>
    </section>

    <template v-if="data?.success">
      <section class="panel">
        <h2 class="h2">组合净值曲线</h2>
        <div class="chart-wrap">
          <v-chart class="chart" :option="chartOption" autoresize />
        </div>
      </section>

      <section class="panel">
        <h2 class="h2">组合指标</h2>
        <div class="grid3">
          <div v-for="row in STAT_ROWS" :key="row.key" class="stat">
            <span class="stat-label">{{ row.label }}</span>
            <span class="stat-val">{{ row.fmt(statValue(row.key)) }}</span>
          </div>
        </div>
      </section>

      <section class="panel">
        <h2 class="h2">标的明细</h2>
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th class="left">标的</th>
                <th>权重</th>
                <th>单标的收益 %</th>
                <th>成交笔数</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in data.per_symbol" :key="p.vt_symbol">
                <td class="left">{{ p.vt_symbol }}</td>
                <td>{{ ((data.weights?.find((w) => w.vt_symbol === p.vt_symbol)?.weight ?? 0) * 100).toFixed(0) }}%</td>
                <td>{{ p.ok ? fmtNum(p.total_return) : '—' }}</td>
                <td>{{ p.ok ? p.trade_count : '—' }}</td>
                <td>{{ p.ok ? '✓' : p.error }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; padding: 5.5rem 1.2rem 4rem; max-width: 1100px; margin: 0 auto; }
.head { margin-bottom: 1.2rem; }
.title { display: flex; align-items: center; gap: .5rem; margin: 0; font-size: 1.45rem; color: var(--bq-text); }
.lead { margin: .4rem 0 0; color: var(--bq-muted); font-size: .9rem; }
.panel { margin-bottom: 1rem; padding: 1rem; border-radius: .9rem; background: var(--bq-bg-elevated); border: 1px solid rgba(255,255,255,.06); }
.controls-top { display: flex; flex-wrap: wrap; gap: .6rem; align-items: end; }
.fld { display: grid; gap: .25rem; font-size: .78rem; color: var(--bq-muted); }
.fld input, .fld select { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .45rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); }
.btn { display: inline-flex; align-items: center; gap: .35rem; border: 1px solid rgba(255,255,255,.14); border-radius: 999px; padding: .5rem .9rem; font-size: .82rem; background: transparent; color: var(--bq-text); cursor: pointer; }
.btn.primary { background: #2563eb; border-color: transparent; color: #fff; }
.btn:disabled, .icon-btn:disabled { opacity: .5; cursor: not-allowed; }
.ic { width: 1rem; height: 1rem; }
.spin { animation: sp 1s linear infinite; }
@keyframes sp { to { transform: rotate(360deg); } }
.mono { font-family: ui-monospace, monospace; }
.symbols { margin-top: .9rem; display: grid; gap: .45rem; }
.sym-row { display: flex; align-items: center; gap: .5rem; }
.sym-row .mono { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .4rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); width: 200px; }
.w-input { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .4rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); width: 76px; }
.w-pct { width: 42px; color: var(--bq-muted); font-size: .8rem; }
.icon-btn { display: inline-flex; align-items: center; border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .4rem; background: transparent; color: var(--bq-muted); cursor: pointer; }
.icon-btn.danger:hover { color: #f87171; }
.sym-actions { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; margin-top: .2rem; }
.w-sum { color: var(--bq-muted); font-size: .8rem; }
.err { margin: .7rem 0 0; color: #f87171; font-size: .82rem; }
.ok { margin: .7rem 0 0; color: #4ade80; font-size: .82rem; }
.h2 { margin: 0 0 .7rem; font-size: .95rem; color: var(--bq-text); }
.chart-wrap { height: 320px; }
.chart { width: 100%; height: 100%; }
.grid3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .6rem; }
.stat { display: grid; gap: .25rem; padding: .7rem; border: 1px solid rgba(255,255,255,.08); border-radius: .7rem; }
.stat-label { font-size: .72rem; color: var(--bq-muted); }
.stat-val { font-size: 1.15rem; font-weight: 700; color: #f0b429; }
.table-wrap { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: .82rem; }
.tbl th, .tbl td { padding: .45rem .6rem; border-bottom: 1px solid rgba(255,255,255,.06); color: var(--bq-text); text-align: right; white-space: nowrap; }
.tbl th.left, .tbl td.left { text-align: left; }

@media (max-width: 640px) {
  .page { padding: 5rem 0.7rem 2.5rem; }
  .fld { flex: 1 1 100%; }
  .fld input, .fld select { width: 100%; }
  .controls-top .btn { flex: 1 1 100%; justify-content: center; }
  .sym-row { flex-wrap: wrap; }
  .sym-row .mono { width: 100%; }
  .w-input { flex: 1; width: auto; }
  .chart-wrap { height: 260px; }
  .tbl { font-size: .74rem; }
  .tbl th, .tbl td { padding: .35rem .4rem; }
}
</style>