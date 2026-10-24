<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import VChart from 'vue-echarts'
import { ShieldCheck, Play, Loader2, RotateCcw } from 'lucide-vue-next'
import { listStrategies, type StrategyListItem } from '../services/backtest'
import {
  pollJob,
  submitWalkForwardJob,
  runWalkForward,
  type JobInfo,
  type WalkForwardPayload,
} from '../services/analytics'
import { defaultChartEndDate, defaultChartStartDate } from '../services/market'

const strategies = ref<StrategyListItem[]>([])
const sid = ref('01')
const paramName = ref('fast_window')
const valuesText = ref('5,10,15,20,25')
const vtSymbol = ref('600519.SSE')
const start = ref(defaultChartStartDate(4))
const end = ref(defaultChartEndDate())
const nSplits = ref(4)
const trainRatio = ref(0.7)
const embargoDays = ref(5)
const objective = ref<'sharpe' | 'total_return' | 'calmar'>('sharpe')
const useRiskGate = ref(true)

const loading = ref(false)
const progress = ref(0)
const stage = ref('')
const err = ref('')
const data = ref<WalkForwardPayload | null>(null)
let stopPoll: (() => void) | null = null

const paramCandidates = ['fast_window', 'slow_window', 'signal_window', 'atr_window', 'atr_mult', 'fixed_size']

function parseValues(text: string): number[] {
  return text
    .split(/[,，\s]+/)
    .map((s) => Number(s.trim()))
    .filter((n) => !Number.isNaN(n) && n > 0)
}

function fmt(v: number | null | undefined, d = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return Number(v).toFixed(d)
}

const riskColor = computed(() => {
  const p = data.value?.overfit_probability ?? 0
  if (p >= 0.6) return '#f87171'
  if (p >= 0.3) return '#f0b429'
  return '#4ade80'
})

const efficiencyPct = computed(() => Math.round((data.value?.efficiency_ratio ?? 0) * 100))

const foldChart = computed<EChartsOption>(() => {
  const folds = data.value?.folds ?? []
  const labels = folds.map((f) => `折 ${f.fold + 1}`)
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#8b9bb4', fontSize: 11 } },
    grid: { left: 56, right: 24, top: 40, bottom: 40 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { color: '#7f8ea3', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      name: objective.value,
      nameTextStyle: { color: '#7f8ea3' },
      axisLabel: { color: '#7f8ea3', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,.06)' } },
    },
    series: [
      {
        name: '样本内',
        type: 'bar',
        data: folds.map((f) => f.in_sample_score ?? null),
        itemStyle: { color: '#5aa9ff' },
        barMaxWidth: 28,
      },
      {
        name: '样本外',
        type: 'bar',
        data: folds.map((f) => f.oos_score ?? null),
        itemStyle: {
          color: (p: { dataIndex?: number }) => {
            const v = folds[p.dataIndex ?? 0]?.oos_score ?? 0
            return v > 0 ? '#4ade80' : '#f87171'
          },
        },
        barMaxWidth: 28,
      },
    ],
  }
})

const labelOf = computed(() => {
  const s = strategies.value.find((x) => x.strategy_id === sid.value)
  return s ? `${s.strategy_id} · ${s.class_name}` : sid.value
})

async function run() {
  const values = parseValues(valuesText.value)
  if (values.length < 2) {
    err.value = '至少输入 2 个候选参数取值（逗号分隔）'
    return
  }
  loading.value = true
  err.value = ''
  data.value = null
  progress.value = 0
  stage.value = '提交任务'
  const payload = {
    strategy_id: sid.value,
    param_name: paramName.value,
    values,
    vt_symbol: vtSymbol.value.trim(),
    start: start.value,
    end: end.value,
    n_splits: nSplits.value,
    train_ratio: trainRatio.value,
    embargo_days: embargoDays.value,
    objective: objective.value,
    apply_risk_gate: useRiskGate.value,
  }
  try {
    const job = await submitWalkForwardJob(payload)
    stage.value = '排队中'
    await new Promise<void>((resolve, reject) => {
      stopPoll = pollJob(job.job_id, {
        onUpdate: (info: JobInfo) => {
          progress.value = info.progress
          stage.value = info.stage || info.status
          if (info.status === 'done') {
            data.value = info.result as WalkForwardPayload
            resolve()
          }
        },
        onDone: () => resolve(),
        onError: (e) => {
          err.value = e.message
          reject(e)
        },
      })
    })
  } catch (e) {
    // job 接口不可用时降级为同步调用
    if (!data.value) {
      try {
        stage.value = '同步执行（可能较慢）'
        data.value = await runWalkForward(payload)
      } catch (e2) {
        err.value = e2 instanceof Error ? e2.message : e instanceof Error ? e.message : '前向验证失败'
      }
    }
  } finally {
    loading.value = false
    if (stopPoll) {
      stopPoll()
      stopPoll = null
    }
  }
}

function reset() {
  data.value = null
  err.value = ''
  progress.value = 0
  stage.value = ''
}

onMounted(async () => {
  try {
    strategies.value = await listStrategies()
    if (strategies.value[0]) sid.value = strategies.value[0].strategy_id
  } catch (e) {
    err.value = e instanceof Error ? e.message : '策略清单加载失败'
  }
})

onUnmounted(() => {
  if (stopPoll) stopPoll()
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title"><ShieldCheck class="ic" /> 前向验证 / 过拟合检测</h1>
        <p class="lead">
          把区间切成 train/test 多折：只在 train 上选参数，到 test 上看样本外表现。
          回答的不是「哪个参数收益最高」，而是「这个最优参数到了样本外还成立吗」。
        </p>
      </div>
    </header>

    <section class="panel">
      <div class="controls">
        <label class="fld">
          <span>策略</span>
          <select v-model="sid">
            <option v-for="s in strategies" :key="s.strategy_id" :value="s.strategy_id">
              {{ s.strategy_id }} · {{ s.class_name }}
            </option>
          </select>
        </label>
        <label class="fld">
          <span>寻优参数</span>
          <select v-model="paramName">
            <option v-for="p in paramCandidates" :key="p" :value="p">{{ p }}</option>
          </select>
        </label>
        <label class="fld">
          <span>候选值（逗号分隔）</span>
          <input v-model="valuesText" placeholder="5,10,15,20,25" />
        </label>
        <label class="fld">
          <span>vn.py 标的</span>
          <input v-model="vtSymbol" placeholder="600519.SSE" />
        </label>
      </div>
      <div class="controls">
        <label class="fld">
          <span>开始</span>
          <input v-model="start" type="date" />
        </label>
        <label class="fld">
          <span>结束</span>
          <input v-model="end" type="date" />
        </label>
        <label class="fld">
          <span>折数</span>
          <input v-model.number="nSplits" type="number" min="2" max="8" />
        </label>
        <label class="fld">
          <span>train 占比</span>
          <input v-model.number="trainRatio" type="number" min="0.5" max="0.9" step="0.05" />
        </label>
        <label class="fld">
          <span>embargo 天数</span>
          <input v-model.number="embargoDays" type="number" min="0" max="30" />
        </label>
        <label class="fld">
          <span>折内目标</span>
          <select v-model="objective">
            <option value="sharpe">夏普</option>
            <option value="total_return">总收益</option>
            <option value="calmar">Calmar</option>
          </select>
        </label>
        <label class="fld check">
          <input v-model="useRiskGate" type="checkbox" />
          <span>风控闸门过滤</span>
        </label>
      </div>
      <div class="actions">
        <button class="btn primary" :disabled="loading" @click="run">
          <Loader2 v-if="loading" class="ic spin" />
          <Play v-else class="ic" />
          {{ loading ? `验证中 ${progress}%` : '开始前向验证' }}
        </button>
        <button v-if="data" class="btn ghost" @click="reset">
          <RotateCcw class="ic" /> 清空
        </button>
        <span v-if="loading && stage" class="stage">{{ stage }}</span>
      </div>
      <div v-if="loading" class="progress-track">
        <div class="progress-bar" :style="{ width: `${progress}%` }" />
      </div>
      <p class="hint">候选值越多、折数越多，耗时越长。建议先用参数网格粗扫，再拿 Top 5 来做前向验证。</p>
      <p v-if="err" class="err">{{ err }}</p>
    </section>

    <template v-if="data?.ok">
      <section class="panel verdict-panel">
        <div class="verdict-grid">
          <div class="metric">
            <span class="metric-label">样本外效率比</span>
            <strong class="metric-value" :style="{ color: riskColor }">{{ efficiencyPct }}%</strong>
            <span class="metric-hint">样本外得分 / 样本内得分</span>
          </div>
          <div class="metric">
            <span class="metric-label">过拟合概率（估计）</span>
            <strong class="metric-value" :style="{ color: riskColor }">
              {{ Math.round((data.overfit_probability ?? 0) * 100) }}%
            </strong>
            <span class="metric-hint">越高越不可信</span>
          </div>
          <div class="metric">
            <span class="metric-label">样本外一致性</span>
            <strong class="metric-value">{{ Math.round((data.consistency ?? 0) * 100) }}%</strong>
            <span class="metric-hint">样本外得分为正的折占比</span>
          </div>
          <div class="metric">
            <span class="metric-label">通过折数</span>
            <strong class="metric-value">{{ data.folds.filter((f) => f.ok).length }}/{{ data.folds.length }}</strong>
            <span class="metric-hint">{{ labelOf }}</span>
          </div>
        </div>
        <p class="verdict">{{ data.verdict }}</p>
      </section>

      <section class="panel">
        <h2 class="h2">每折样本内 vs 样本外（{{ data.objective }}）</h2>
        <div class="chart-wrap">
          <v-chart class="chart" :option="foldChart" autoresize />
        </div>
      </section>

      <section class="panel">
        <h2 class="h2">逐折明细</h2>
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>折</th>
                <th>train 区间</th>
                <th>test 区间</th>
                <th>最优参数</th>
                <th>样本内</th>
                <th>样本外</th>
                <th>退化</th>
                <th>样本外收益 %</th>
                <th>样本外回撤 %</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="f in data.folds" :key="f.fold" :class="{ failed: !f.ok }">
                <td>#{{ f.fold + 1 }}</td>
                <td class="mono">{{ f.train_start }} ~ {{ f.train_end }}</td>
                <td class="mono">{{ f.test_start }} ~ {{ f.test_end }}</td>
                <td class="mono">
                  {{ f.best_params ? Object.entries(f.best_params).map(([k, v]) => `${k}=${v}`).join(', ') : '—' }}
                </td>
                <td>{{ fmt(f.in_sample_score) }}</td>
                <td :style="{ color: (f.oos_score ?? 0) > 0 ? '#4ade80' : '#f87171' }">
                  {{ f.ok ? fmt(f.oos_score) : '失败' }}
                </td>
                <td>{{ f.degradation == null ? '—' : `${(f.degradation * 100).toFixed(1)}%` }}</td>
                <td>{{ fmt(f.oos_return) }}</td>
                <td>{{ f.oos_max_drawdown == null ? '—' : fmt(Math.abs(f.oos_max_drawdown)) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="hint">{{ data.message }}</p>
      </section>
    </template>

    <p v-else-if="data && !data.ok" class="err box">{{ data.reason || '前向验证失败' }}</p>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; padding: 5.5rem 1.2rem 4rem; max-width: 1150px; margin: 0 auto; }
.head { margin-bottom: 1.2rem; }
.title { display: flex; align-items: center; gap: .5rem; margin: 0; font-size: 1.45rem; color: var(--bq-text); }
.lead { margin: .4rem 0 0; color: var(--bq-muted); font-size: .88rem; line-height: 1.7; max-width: 900px; }
.panel { margin-bottom: 1rem; padding: 1rem; border-radius: .9rem; background: var(--bq-bg-elevated); border: 1px solid rgba(255,255,255,.06); }
.controls { display: flex; flex-wrap: wrap; gap: .6rem; align-items: end; margin-bottom: .5rem; }
.fld { display: grid; gap: .25rem; font-size: .78rem; color: var(--bq-muted); }
.fld.check { display: flex; align-items: center; gap: .4rem; padding-bottom: .5rem; }
.fld input, .fld select { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .45rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); }
.fld input:not([type='checkbox']) { width: 160px; }
.actions { display: flex; align-items: center; gap: .6rem; margin-top: .5rem; }
.btn { display: inline-flex; align-items: center; gap: .35rem; border: 0; border-radius: 999px; padding: .55rem 1rem; font-size: .85rem; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; }
.btn.ghost { background: transparent; color: var(--bq-text); border: 1px solid rgba(255,255,255,.16); }
.btn:disabled { opacity: .55; cursor: not-allowed; }
.ic { width: 1rem; height: 1rem; }
.spin { animation: sp 1s linear infinite; }
@keyframes sp { to { transform: rotate(360deg); } }
.stage { color: var(--bq-muted); font-size: .78rem; }
.progress-track { height: 6px; margin-top: .7rem; border-radius: 999px; background: rgba(255,255,255,.08); overflow: hidden; }
.progress-bar { height: 100%; background: linear-gradient(90deg, #2563eb, #22d3ee); transition: width .3s; }
.err { margin: .6rem 0 0; color: #f87171; font-size: .82rem; }
.err.box { padding: 1rem; border: 1px solid rgba(248,113,113,.3); border-radius: .7rem; background: rgba(248,113,113,.06); }
.hint { margin: .6rem 0 0; color: var(--bq-muted); font-size: .76rem; line-height: 1.6; }
.h2 { margin: 0 0 .7rem; font-size: .95rem; color: var(--bq-text); }
.verdict-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: .7rem; }
.metric { display: flex; flex-direction: column; gap: .2rem; padding: .7rem .8rem; border-radius: .6rem; background: rgba(255,255,255,.03); }
.metric-label { font-size: .72rem; color: #8b9bb4; }
.metric-value { font-size: 1.4rem; color: var(--bq-text); font-variant-numeric: tabular-nums; }
.metric-hint { font-size: .68rem; color: #6f7f94; }
.verdict { margin: .9rem 0 0; padding: .7rem .8rem; border-left: 3px solid #5aa9ff; background: rgba(90,169,255,.07); color: #c3d2e8; font-size: .84rem; line-height: 1.7; }
.chart-wrap { height: 340px; }
.chart { width: 100%; height: 100%; }
.table-wrap { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: .78rem; }
.tbl th, .tbl td { padding: .45rem .55rem; border-bottom: 1px solid rgba(255,255,255,.06); color: var(--bq-text); text-align: right; white-space: nowrap; }
.tbl th:first-child, .tbl td:first-child { text-align: left; }
.tbl tr.failed { opacity: .55; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #9fb3cc; }
</style>
