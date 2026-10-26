<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import VChart from 'vue-echarts'
import { Grid3x3, Play, Loader2, X, ShieldCheck } from 'lucide-vue-next'
import { listStrategies, type StrategyListItem } from '../services/backtest'
import { pollJob, runGrid, submitGridJob, cancelJob, runStability, type GridPayload, type JobInfo, type StabilityPayload } from '../services/analytics'
import { defaultChartEndDate, defaultChartStartDate } from '../services/market'

const strategies = ref<StrategyListItem[]>([])
const sid = ref('01')
const paramName = ref('fast_window')
const valuesText = ref('5,10,15,20,25')
const vtSymbol = ref('600519.SSE')
const start = ref(defaultChartStartDate(2))
const end = ref(defaultChartEndDate())

const use2D = ref(false)
const param2 = ref('slow_window')
const values2Text = ref('20,30,40,50,60')

const loading = ref(false)
const progress = ref(0)
const stage = ref('')
const err = ref('')
const data = ref<GridPayload | null>(null)
let stopPoll: (() => void) | null = null
let activeJobId = ref('')

const paramCandidates = [
  'fast_window',
  'slow_window',
  'signal_window',
  'atr_window',
  'atr_mult',
  'fixed_size',
  // 止损维度：0 = 关闭，可扫描「均线窗口 × 止损幅度」看止损是否真有价值
  'stop_loss_pct',
  'take_profit_pct',
  'trailing_stop_pct',
]
const STOP_PARAMS = new Set(['stop_loss_pct', 'take_profit_pct', 'trailing_stop_pct'])

const stability = ref<StabilityPayload | null>(null)
const stabilityLoading = ref(false)
const stabilityErr = ref('')

function parseValues(text: string, allowZero = false): number[] {
  return text
    .split(/[,，\s]+/)
    .map((s) => Number(s.trim()))
    .filter((n) => !Number.isNaN(n) && (allowZero ? n >= 0 : n > 0))
}

async function run() {
  const values = parseValues(valuesText.value, STOP_PARAMS.has(paramName.value))
  if (values.length < 2) {
    err.value = '至少输入 2 个参数取值（逗号分隔；止损参数可含 0）'
    return
  }
  const v2 = parseValues(values2Text.value, use2D.value && STOP_PARAMS.has(param2.value))
  if (use2D.value && v2.length < 2) {
    err.value = '双因子模式第二维至少需要 2 个取值'
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
    param2: use2D.value ? param2.value : undefined,
    values2: use2D.value ? v2 : undefined,
    vt_symbol: vtSymbol.value.trim(),
    start: start.value,
    end: end.value,
  }
  try {
    const job = await submitGridJob(payload)
    activeJobId.value = job.job_id
    stage.value = '排队中'
    await new Promise<void>((resolve, reject) => {
      stopPoll = pollJob(job.job_id, {
        onUpdate: (info: JobInfo) => {
          progress.value = info.progress
          stage.value = info.stage || info.status
          if (info.status === 'done') {
            data.value = info.result as GridPayload
            resolve()
          }
        },
        onDone: () => resolve(),
        onError: (e) => reject(e),
      })
    })
  } catch (e) {
    // 任务接口不可用时降级为同步调用
    if (!data.value) {
      try {
        stage.value = '同步执行（可能较慢）'
        data.value = await runGrid(payload)
      } catch (e2) {
        err.value = e2 instanceof Error ? e2.message : e instanceof Error ? e.message : '扫描失败'
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

function cancel() {
  if (activeJobId.value) void cancelJob(activeJobId.value).catch(() => undefined)
  stopPoll?.()
  stopPoll = null
  loading.value = false
  progress.value = 0
  stage.value = ''
  activeJobId.value = ''
}

async function checkStability() {
  const payload = data.value
  if (!payload || payload.mode === '2d' || !payload.cells?.length) return
  const objective = (payload.objective ?? 'sharpe') as 'sharpe' | 'total_return'
  const picks = payload.cells.filter((c) => c.ok)
  if (picks.length < 3) {
    stabilityErr.value = '有效参数点少于 3 个，无法评估稳定性'
    return
  }
  stabilityLoading.value = true
  stabilityErr.value = ''
  stability.value = null
  try {
    stability.value = await runStability({
      strategy_id: sid.value,
      param_name: paramName.value,
      values: picks.map((c) => c.value),
      objective,
      // 复用已扫出的分数，不再重复跑回测
      precomputed_scores: picks.map((c) => (objective === 'total_return' ? c.total_return ?? null : c.sharpe ?? null)),
      vt_symbol: payload.vt_symbol,
      start: payload.start,
      end: payload.end,
    })
  } catch (e) {
    stabilityErr.value = e instanceof Error ? e.message : '稳定性检测失败'
  } finally {
    stabilityLoading.value = false
  }
}

const heatOption = computed(() => {
  const values = data.value?.values ?? []
  const values2 = data.value?.values2 ?? []
  const matrix = data.value?.matrix ?? []
  const cellData: [number, number, number][] = []
  matrix.forEach((row, i) => {
    row.forEach((v, j) => {
      if (v !== null && v !== undefined && !Number.isNaN(v)) cellData.push([j, i, v])
    })
  })
  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      formatter: (params: unknown) => {
        const p = params as { value: [number, number, number] }
        const [, i, v] = p.value
        const p1 = values[i]
        const p2 = values2[Math.floor(p.value[0])]
        return `${data.value?.param_name}=${p1}<br/>${data.value?.param2}=${p2}<br/>总收益：${v.toFixed(3)}%`
      },
    },
    grid: { left: 72, right: 24, top: 24, bottom: 64 },
    xAxis: {
      type: 'category',
      data: values2,
      name: data.value?.param2 ?? '参数2',
      nameTextStyle: { color: '#7f8ea3' },
      axisLabel: { color: '#7f8ea3', fontSize: 10 },
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: values,
      name: data.value?.param_name ?? '参数1',
      nameTextStyle: { color: '#7f8ea3' },
      axisLabel: { color: '#7f8ea3', fontSize: 10 },
      splitArea: { show: true },
    },
    visualMap: {
      min: -10,
      max: 20,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#2563eb', '#3b82f6', '#f59e0b', '#ef4444'] },
    },
    series: [
      {
        type: 'heatmap',
        data: cellData,
        label: { show: true, color: '#fff', fontSize: 10, formatter: (p: { value: number[] }) => (p.value[2] ?? 0).toFixed(1) },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' } },
      },
    ],
  }
})

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

function stabWidth(score: number): string {
  const vals = stability.value?.curve?.map((p) => p.score) ?? []
  const maxAbs = Math.max(...vals.map((v) => Math.abs(v)), 1e-9)
  const pct = Math.max(2, Math.min(100, (Math.abs(score) / maxAbs) * 100))
  return `${pct}%`
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
        <p class="lead">单参数扫描或双参数热力图，观察总收益 / 回撤随参数取值的变化</p>
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
          {{ loading ? `扫描中 ${progress}%` : '开始扫描' }}
        </button>
        <button v-if="loading" class="btn ghost" @click="cancel">
          <X class="ic" /> 取消
        </button>
      </div>
      <div class="controls">
        <label class="fld">
          <span>双因子热力图</span>
          <span class="switch-row">
            <input id="use2d" v-model="use2D" type="checkbox" />
            <label for="use2d">启用第二维参数</label>
          </span>
        </label>
        <label v-if="use2D" class="fld">
          <span>第二维参数</span>
          <select v-model="param2">
            <option v-for="p in paramCandidates.filter((x) => x !== paramName)" :key="p" :value="p">{{ p }}</option>
          </select>
        </label>
        <label v-if="use2D" class="fld">
          <span>第二维取值（逗号分隔）</span>
          <input v-model="values2Text" placeholder="20,30,40,50,60" />
        </label>
        <p class="hint">双因子模式会扫描两参数的全部组合（最多 60 格），用热力图展示总收益分布。</p>
      </div>
      <div v-if="loading" class="progress-track">
        <div class="progress-bar" :style="{ width: `${progress}%` }" />
      </div>
      <p v-if="loading && stage" class="hint">当前：{{ stage }}</p>
      <p v-if="err" class="err">{{ err }}</p>
      <p v-else-if="data" class="ok">
        {{ data.message }}<span v-if="data.cached">（缓存）</span>
      </p>
    </section>

    <template v-if="data?.success">
      <section v-if="data.mode === '2d'" class="panel">
        <h2 class="h2">
          双参数热力图：总收益分布（{{ data.vt_symbol }} {{ data.start }} → {{ data.end }}）
        </h2>
        <div class="chart-wrap">
          <v-chart class="chart" :option="heatOption" autoresize />
        </div>
        <p class="hint" v-if="data.best && (data.best as { p1?: number }).p1 != null">
          最佳组合：{{ data.param_name }}={{ (data.best as { p1?: number }).p1 }} · {{ data.param2 }}={{ (data.best as { p2?: number }).p2 }}（总收益 {{ (data.best as { total_return?: number }).total_return }}%）
        </p>
      </section>

      <section v-if="data.mode !== '2d'" class="panel">
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

      <section v-if="data.mode !== '2d'" class="panel">
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

      <section v-if="data.mode !== '2d'" class="panel">
        <h2 class="h2">参数稳定性 / 过拟合检测</h2>
        <p class="hint">
          直接复用上面已扫描的分数，不重跑回测：看最优参数是「平滑过渡」还是「孤立尖峰」。
          孤立尖峰说明最优值大概率命中了样本噪声。
        </p>
        <button class="btn primary" :disabled="stabilityLoading" @click="checkStability">
          <Loader2 v-if="stabilityLoading" class="ic spin" />
          <ShieldCheck v-else class="ic" />
          {{ stabilityLoading ? '检测中...' : '检测参数稳定性' }}
        </button>
        <p v-if="stabilityErr" class="err">{{ stabilityErr }}</p>

        <div v-if="stability?.ok" class="stability">
          <div class="stab-head">
            <span class="stab-badge" :class="stability.isolated_peak ? 'bad' : 'ok'">
              {{ stability.isolated_peak ? '孤立尖峰 · 过拟合风险高' : '参数曲面平滑' }}
            </span>
            <span class="stab-meta">
              最优 {{ stability.param_name }} = {{ stability.best_param }} · 最优分 {{ fmt(stability.best_score, 4) }} ·
              邻居均值 {{ fmt(stability.neighbor_avg, 4) }} · 平滑度 {{ fmt(stability.smoothness, 3) }}
            </span>
          </div>
          <p class="stab-verdict">{{ stability.verdict }}</p>
          <div class="stab-curve">
            <div v-for="p in stability.curve ?? []" :key="p.param" class="stab-point">
              <span class="sp-param">{{ p.param }}</span>
              <div class="sp-track">
                <div class="sp-bar" :style="{ width: stabWidth(p.score) }" :class="{ peak: p.param === stability.best_param }" />
              </div>
              <span class="sp-score">{{ fmt(p.score, 4) }}</span>
            </div>
          </div>
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
.btn.ghost { background: transparent; color: var(--bq-text); border: 1px solid rgba(255,255,255,.16); }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.progress-track { height: 6px; margin-top: .7rem; border-radius: 999px; background: rgba(255,255,255,.08); overflow: hidden; }
.progress-bar { height: 100%; background: linear-gradient(90deg, #2563eb, #22d3ee); transition: width .3s; }
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
.chart-wrap { height: 420px; }
.chart { width: 100%; height: 100%; }
.switch-row { display: flex; align-items: center; gap: .35rem; padding-top: .3rem; }
.switch-row label { color: var(--bq-muted); font-size: .78rem; }
.hint { margin: .5rem 0 0; font-size: .76rem; color: var(--bq-muted); }

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

.stability { margin-top: .9rem; }
.stab-head { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem; }
.stab-badge { padding: .2rem .6rem; border-radius: 999px; font-size: .72rem; font-weight: 600; }
.stab-badge.ok { background: rgba(34,197,94,.14); color: #4ade80; }
.stab-badge.bad { background: rgba(248,113,113,.14); color: #f87171; }
.stab-meta { color: var(--bq-muted); font-size: .74rem; }
.stab-verdict { margin: .6rem 0; padding: .55rem .7rem; border-left: 3px solid #5aa9ff; background: rgba(90,169,255,.07); color: #c3d2e8; font-size: .8rem; line-height: 1.65; }
.stab-curve { display: grid; gap: .3rem; }
.stab-point { display: grid; grid-template-columns: 70px 1fr 70px; gap: .5rem; align-items: center; font-size: .75rem; }
.sp-param { text-align: right; color: var(--bq-muted); }
.sp-track { height: 10px; border-radius: 999px; background: rgba(255,255,255,.06); overflow: hidden; }
.sp-bar { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #2563eb, #22d3ee); }
.sp-bar.peak { background: linear-gradient(90deg, #f59e0b, #f87171); }
.sp-score { color: var(--bq-text); text-align: right; font-variant-numeric: tabular-nums; }
</style>