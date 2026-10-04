<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Grid3x3, Play, Loader2 } from 'lucide-vue-next'
import { listStrategies, type StrategyListItem } from '../services/backtest'
import { runGrid, type GridPayload } from '../services/analytics'
import { defaultChartEndDate, defaultChartStartDate } from '../services/market'

const strategies = ref<StrategyListItem[]>([])
const sid = ref('01')
const paramName = ref('fast_window')
const valuesText = ref('5,10,15,20,25')
const vtSymbol = ref('600519.SSE')
const start = ref(defaultChartStartDate(2))
const end = ref(defaultChartEndDate())

const loading = ref(false)
const err = ref('')
const data = ref<GridPayload | null>(null)

const paramCandidates = ['fast_window', 'slow_window', 'signal_window', 'atr_window', 'atr_mult', 'fixed_size']

function parseValues(): number[] {
  return valuesText.value
    .split(/[,，\s]+/)
    .map((s) => Number(s.trim()))
    .filter((n) => !Number.isNaN(n) && n > 0)
}

async function run() {
  const values = parseValues()
  if (values.length < 2) {
    err.value = '至少输入 2 个参数取值（逗号分隔）'
    return
  }
  loading.value = true
  err.value = ''
  try {
    data.value = await runGrid({
      strategy_id: sid.value,
      param_name: paramName.value,
      values,
      vt_symbol: vtSymbol.value.trim(),
      start: start.value,
      end: end.value,
    })
  } catch (e) {
    err.value = e instanceof Error ? e.message : '扫描失败'
    data.value = null
  } finally {
    loading.value = false
  }
}

const series = computed(() => ({
  values: data.value?.cells.filter((c) => c.ok).map((c) => c.value) ?? [],
  rets: data.value?.cells.filter((c) => c.ok).map((c) => c.total_return) ?? [],
  dds: data.value?.cells.filter((c) => c.ok).map((c) => c.max_drawdown) ?? [],
}))

function fmt(v: number | null | undefined, d = 2) {
  return v === null || v === undefined || Number.isNaN(v) ? '—' : `${Number(v).toFixed(d)}`
}

function barW(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return 0
  const maxAbs = Math.max(
    ...(data.value?.cells.filter((c) => c.ok && c.total_return != null).map((c) => Math.abs(c.total_return ?? 0)) ?? [1]),
    1,
  )
  return Math.max(2, Math.min(100, (Math.abs(v) / maxAbs) * 100))
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
        <h1 class="title"><Grid3x3 class="ic" /> 参数网格优化</h1>
        <p class="lead">单参数网格扫描，观察总收益 / 最大回撤随参数取值的变化</p>
      </div>
    </header>

    <section class="panel">
      <div class="controls">
        <label class="fld">
          <span>策略</span>
          <select v-model="sid">
            <option v-for="s in strategies" :key="s.strategy_id" :value="s.strategy_id">
              {{ s.strategy_id }} · {{ s.class_name ?? '' }}
            </option>
          </select>
        </label>
        <label class="fld">
          <span>扫描参数</span>
          <select v-model="paramName">
            <option v-for="p in paramCandidates" :key="p" :value="p">{{ p }}</option>
          </select>
        </label>
        <label class="fld">
          <span>取值（逗号分隔）</span>
          <input v-model="valuesText" placeholder="5,10,15,20,25" />
        </label>
        <label class="fld">
          <span>vn.py 标的</span>
          <input v-model="vtSymbol" placeholder="600519.SSE" />
        </label>
        <button class="btn primary" :disabled="loading" @click="run">
          <Loader2 v-if="loading" class="ic spin" />
          <Play v-else class="ic" />
          {{ loading ? '扫描中…' : '开始扫描' }}
        </button>
      </div>
      <p v-if="err" class="err">{{ err }}</p>
      <p v-else-if="data" class="ok">
        {{ data.message }}<span v-if="data.cached">（缓存）</span>
      </p>
    </section>

    <template v-if="data?.success">
      <section class="panel">
        <h2 class="h2">总收益 / 回撤 扫描（{{ data.vt_symbol }} {{ data.start }} → {{ data.end }}）</h2>
        <div class="bar-list">
          <div v-for="c in data.cells.filter((x) => x.ok)" :key="c.value" class="bar-row">
            <span class="bar-label">{{ paramName }} = {{ c.value }}</span>
            <div class="bar-track">
              <div
                class="bar ret"
                :class="{ best: data.best && c.value === data.best.value }"
                :style="{ width: `${barW(c.total_return)}%` }"
              />
            </div>
            <span
              class="bar-val ret"
              :class="{ best: data.best && c.value === data.best.value }"
            >{{ fmt(c.total_return) }}%</span>
            <span class="bar-val muted">{{ fmt(c.max_drawdown) }}%</span>
            <span class="bar-val muted">{{ c.trade_count }}笔</span>
          </div>
        </div>
      </section>

      <section class="panel">
        <h2 class="h2">明细</h2>
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>{{ paramName }}</th>
                <th>总收益 %</th>
                <th>年化 %</th>
                <th>最大回撤 %</th>
                <th>夏普</th>
                <th>成交笔数</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="c in data.cells"
                :key="c.value"
                :class="{ bestrow: data.best && c.value === data.best.value }"
              >
                <td>{{ c.value }}</td>
                <td>{{ c.ok ? fmt(c.total_return) : c.error }}</td>
                <td>{{ c.ok ? fmt(c.annual_return) : '—' }}</td>
                <td>{{ c.ok ? fmt(c.max_drawdown) : '—' }}</td>
                <td>{{ c.ok ? fmt(c.sharpe) : '—' }}</td>
                <td>{{ c.ok ? c.trade_count : '—' }}</td>
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
.controls { display: flex; flex-wrap: wrap; gap: .6rem; align-items: end; }
.fld { display: grid; gap: .25rem; font-size: .78rem; color: var(--bq-muted); }
.fld input, .fld select { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .45rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); }
.fld input { width: 190px; }
.btn { display: inline-flex; align-items: center; gap: .35rem; border: 0; border-radius: 999px; padding: .55rem 1rem; font-size: .85rem; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.ic { width: 1rem; height: 1rem; }
.spin { animation: sp 1s linear infinite; }
@keyframes sp { to { transform: rotate(360deg); } }
.err { margin: .6rem 0 0; color: #f87171; font-size: .82rem; }
.ok { margin: .6rem 0 0; color: #4ade80; font-size: .82rem; }
.h2 { margin: 0 0 .7rem; font-size: .95rem; color: var(--bq-text); }
.bar-list { display: grid; gap: .35rem; }
.bar-row { display: grid; grid-template-columns: 130px 1fr 70px 70px 60px; gap: .4rem; align-items: center; font-size: .76rem; color: var(--bq-text); }
.bar-label { text-align: right; white-space: nowrap; color: var(--bq-muted); }
.bar-track { height: 12px; background: rgba(255,255,255,.06); border-radius: 999px; overflow: hidden; }
.bar.ret { height: 100%; background: linear-gradient(90deg, #2563eb, #22d3ee); border-radius: 999px; }
.bar.ret.best { background: linear-gradient(90deg, #22c55e, #4ade80); }
.bar-val.ret { color: #4ade80; font-weight: 600; }
.bar-val.ret.best { color: #86efac; }
.bar-val.muted { color: var(--bq-muted); }
.table-wrap { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: .82rem; }
.tbl th, .tbl td { padding: .45rem .6rem; border-bottom: 1px solid rgba(255,255,255,.06); color: var(--bq-text); text-align: right; white-space: nowrap; }
.bestrow { background: rgba(34,197,94,.08); }

@media (max-width: 640px) {
  .page { padding: 5rem 0.7rem 2.5rem; }
  .fld { flex: 1 1 100%; }
  .fld input, .fld select { width: 100%; }
  .controls .btn { flex: 1 1 100%; justify-content: center; }
  .bar-row { grid-template-columns: 1fr 44px 44px 40px; }
  .bar-label { grid-column: 1 / -1; text-align: left; }
  .tbl { font-size: .74rem; }
  .tbl th, .tbl td { padding: .35rem .4rem; }
}
</style>