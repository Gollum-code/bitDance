<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import VChart from 'vue-echarts'
import { GitCompareArrows, Play, Loader2 } from 'lucide-vue-next'
import { listStrategies, type StrategyListItem } from '../services/backtest'
import { runCompare, type ComparePayload } from '../services/analytics'
import { defaultChartEndDate, defaultChartStartDate } from '../services/market'

const strategies = ref<StrategyListItem[]>([])
const selected = ref<string[]>([])
const vtSymbol = ref('600519.SSE')
const start = ref(defaultChartStartDate(2))
const end = ref(defaultChartEndDate())

const loading = ref(false)
const err = ref('')
const data = ref<ComparePayload | null>(null)

const byId = computed(() => {
  const m = new Map<string, StrategyListItem>()
  for (const s of strategies.value) m.set(s.strategy_id, s)
  return m
})

function label(id: string) {
  const s = byId.value.get(id)
  return s ? `${id} ${s.class_name ?? ''}` : id
}

const STAT_ROWS: { key: string; label: string; fmt: (v: unknown) => string; better: 'high' | 'low' | 'none' }[] = [
  { key: 'total_return', label: '总收益率 %', fmt: (v) => fmtNum(v, 2), better: 'high' },
  { key: 'annual_return', label: '年化收益 %', fmt: (v) => fmtNum(v, 2), better: 'high' },
  { key: 'max_drawdown', label: '最大回撤 %', fmt: (v) => fmtNum(v, 2), better: 'high' },
  { key: 'sharpe_ratio', label: '夏普比率', fmt: (v) => fmtNum(v, 2), better: 'high' },
  { key: 'win_rate', label: '胜率 %', fmt: (v) => fmtNum(v, 2), better: 'high' },
  { key: 'total_trade_count', label: '成交笔数', fmt: (v) => fmtNum(v, 0), better: 'none' },
]

function fmtNum(v: unknown, digits: number): string {
  const n = typeof v === 'number' ? v : Number(v)
  if (Number.isNaN(n) || v === null || v === undefined) return '—'
  return n.toFixed(digits)
}

const palette = ['#5aa9ff', '#f0b429', '#4ade80', '#f472b6', '#a78bfa', '#fb923c', '#22d3ee', '#f87171']

const chartOption = computed<EChartsOption>(() => {
  const curves = data.value?.curves ?? {}
  const dates = data.value?.dates ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { type: 'scroll', textStyle: { color: '#8b9bb4', fontSize: 11 } },
    grid: { left: 56, right: 24, top: 40, bottom: 48 },
    xAxis: { type: 'category', data: dates, axisLabel: { color: '#7f8ea3', fontSize: 10 } },
    yAxis: {
      type: 'value',
      name: '累计收益 %',
      nameTextStyle: { color: '#7f8ea3' },
      axisLabel: { color: '#7f8ea3', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,.06)' } },
    },
    series: Object.entries(curves).map(([id, arr], i) => ({
      name: label(id),
      type: 'line',
      smooth: true,
      showSymbol: false,
      connectNulls: true,
      lineStyle: { width: 1.8, color: palette[i % palette.length] },
      itemStyle: { color: palette[i % palette.length] },
      data: arr,
    })),
  }
})

function toggle(id: string) {
  const i = selected.value.indexOf(id)
  if (i >= 0) selected.value.splice(i, 1)
  else if (selected.value.length < 8) selected.value.push(id)
  data.value = null
}

async function run() {
  if (!selected.value.length) {
    err.value = '请至少选择 1 个策略'
    return
  }
  loading.value = true
  err.value = ''
  try {
    data.value = await runCompare({
      strategy_ids: selected.value,
      vt_symbol: vtSymbol.value.trim(),
      start: start.value,
      end: end.value,
    })
  } catch (e) {
    err.value = e instanceof Error ? e.message : '对比失败'
    data.value = null
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    strategies.value = await listStrategies()
  } catch (e) {
    err.value = e instanceof Error ? e.message : '策略清单加载失败'
  }
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title"><GitCompareArrows class="ic" /> 多策略对比</h1>
        <p class="lead">同一标的、同一区间并行回测多个策略，收益曲线叠加 + 指标并排</p>
      </div>
    </header>

    <section class="panel">
      <div class="controls">
        <label class="fld">
          <span>vn.py 标的</span>
          <input v-model="vtSymbol" placeholder="600519.SSE" />
        </label>
        <label class="fld">
          <span>开始</span>
          <input v-model="start" type="date" />
        </label>
        <label class="fld">
          <span>结束</span>
          <input v-model="end" type="date" />
        </label>
        <button class="btn primary" :disabled="loading || !selected.length" @click="run">
          <Loader2 v-if="loading" class="ic spin" />
          <Play v-else class="ic" />
          {{ loading ? '回测中…' : '开始对比' }}
        </button>
      </div>
      <p class="hint">已选 {{ selected.length }}/8 · 需先在「行情」页同步该标的日线到本地库</p>

      <div class="chips">
        <button
          v-for="s in strategies"
          :key="s.strategy_id"
          class="chip"
          :class="{ on: selected.includes(s.strategy_id) }"
          @click="toggle(s.strategy_id)"
        >
          {{ s.strategy_id }} · {{ s.class_name ?? '' }}
        </button>
      </div>
      <p v-if="err" class="err">{{ err }}</p>
      <p v-else-if="data" class="ok">{{ data.message }}</p>
    </section>

    <template v-if="data && data.results.some((r) => r.ok)">
      <section class="panel">
        <div class="chart-wrap">
          <v-chart class="chart" :option="chartOption" autoresize />
        </div>
      </section>

      <section class="panel">
        <h2 class="h2">指标对比</h2>
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th class="left">策略</th>
                <th v-for="r in data.results.filter((x) => x.ok)" :key="r.strategy_id">
                  {{ label(r.strategy_id ?? '') }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in STAT_ROWS" :key="row.key">
                <td class="left">{{ row.label }}</td>
                <td v-for="r in data.results.filter((x) => x.ok)" :key="r.strategy_id">
                  {{ row.fmt(r.stats?.[row.key]) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <ul class="fails">
          <li v-for="r in data.results.filter((x) => !x.ok)" :key="r.strategy_id">
            {{ r.strategy_id }}：{{ r.error }}
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; padding: 5.5rem 1.2rem 4rem; max-width: 1200px; margin: 0 auto; }
.head { margin-bottom: 1.2rem; }
.title { display: flex; align-items: center; gap: .5rem; margin: 0; font-size: 1.45rem; color: var(--bq-text); }
.lead { margin: .4rem 0 0; color: var(--bq-muted); font-size: .9rem; }
.panel { margin-bottom: 1rem; padding: 1rem; border-radius: .9rem; background: var(--bq-bg-elevated); border: 1px solid rgba(255,255,255,.06); }
.controls { display: flex; flex-wrap: wrap; gap: .6rem; align-items: end; }
.fld { display: grid; gap: .25rem; font-size: .78rem; color: var(--bq-muted); }
.fld input { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .45rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); }
.btn { display: inline-flex; align-items: center; gap: .35rem; border: 0; border-radius: 999px; padding: .55rem 1rem; font-size: .85rem; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.ic { width: 1rem; height: 1rem; }
.spin { animation: sp 1s linear infinite; }
@keyframes sp { to { transform: rotate(360deg); } }
.hint { margin: .6rem 0 0; font-size: .78rem; color: var(--bq-muted); }
.chips { margin-top: .8rem; display: flex; flex-wrap: wrap; gap: .35rem; max-height: 160px; overflow-y: auto; }
.chip { border: 1px solid rgba(255,255,255,.12); border-radius: 999px; padding: .28rem .6rem; font-size: .74rem; color: var(--bq-muted); background: transparent; cursor: pointer; }
.chip.on { border-color: #2563eb; color: #93c5fd; background: rgba(37,99,235,.14); }
.err { margin: .6rem 0 0; color: #f87171; font-size: .82rem; }
.ok { margin: .6rem 0 0; color: #4ade80; font-size: .82rem; }
.chart-wrap { height: 380px; }
.chart { width: 100%; height: 100%; }
.h2 { margin: 0 0 .7rem; font-size: .95rem; color: var(--bq-text); }
.table-wrap { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: .82rem; }
.tbl th, .tbl td { padding: .45rem .6rem; border-bottom: 1px solid rgba(255,255,255,.06); color: var(--bq-text); text-align: right; white-space: nowrap; }
.tbl th.left, .tbl td.left { text-align: left; color: var(--bq-muted); }
.fails { margin: .6rem 0 0; padding-left: 1.1rem; font-size: .76rem; color: var(--bq-muted); }

@media (max-width: 640px) {
  .page { padding: 5rem 0.7rem 2.5rem; }
  .fld { flex: 1 1 100%; }
  .fld input { width: 100%; }
  .controls .btn { flex: 1 1 100%; justify-content: center; }
  .chart-wrap { height: 300px; }
  .tbl { font-size: .74rem; }
  .tbl th, .tbl td { padding: .35rem .4rem; }
}
</style>