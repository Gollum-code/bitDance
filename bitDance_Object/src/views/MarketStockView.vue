<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import type { EChartsOption } from 'echarts'
import VChart from 'vue-echarts'
import { Database, Download, LineChart, Upload } from 'lucide-vue-next'
import { downloadCsv } from '../utils/csvExport'
import {
  defaultChartEndDate,
  defaultChartStartDate,
  getMarketDaily,
  getMarketMinute,
  syncMarketToVnpy,
  uploadCsvToVnpy,
  type DailyPayload,
  type MinutePayload,
} from '../services/market'

const route = useRoute()
const router = useRouter()

const tsCode = ref('')
const start = ref(defaultChartStartDate(2))
const end = ref(defaultChartEndDate())
const loading = ref(false)
const syncing = ref(false)
const uploading = ref(false)
const uploadInput = ref<HTMLInputElement | null>(null)
const errorMessage = ref('')
const infoMessage = ref('')
const payload = ref<DailyPayload | null>(null)

const vtSymbol = computed(() => payload.value?.vt_symbol ?? '')

type ViewMode = 'daily' | 'minute'
const viewMode = ref<ViewMode>('daily')
const minutePeriod = ref('m5')
const minutePayload = ref<MinutePayload | null>(null)
const minuteLoading = ref(false)

type Indicator = 'none' | 'boll' | 'macd'
const indicator = ref<Indicator>('none')

function smaArr(arr: number[], window: number): (number | null)[] {
  const out: (number | null)[] = []
  let sum = 0
  for (let i = 0; i < arr.length; i++) {
    sum += arr[i]
    if (i >= window) sum -= arr[i - window]
    out[i] = i >= window - 1 ? sum / window : null
  }
  return out
}

function emaArr(arr: number[], window: number): number[] {
  const k = 2 / (window + 1)
  const out: number[] = []
  let prev = arr[0]
  for (let i = 0; i < arr.length; i++) {
    prev = i === 0 ? arr[0] : arr[i] * k + prev * (1 - k)
    out[i] = prev
  }
  return out
}

function macdArr(closes: number[]): { dif: number[]; dea: number[]; hist: number[] } {
  const ema12 = emaArr(closes, 12)
  const ema26 = emaArr(closes, 26)
  const dif = closes.map((_, i) => ema12[i] - ema26[i])
  const dea = emaArr(dif, 9)
  const hist = dif.map((d, i) => (d - dea[i]) * 2)
  return { dif, dea, hist }
}

function bollArr(closes: number[], window = 20): { mid: (number | null)[]; upper: (number | null)[]; lower: (number | null)[] } {
  const mid = smaArr(closes, window)
  const upper: (number | null)[] = []
  const lower: (number | null)[] = []
  for (let i = 0; i < closes.length; i++) {
    if (mid[i] === null || i < window - 1) {
      upper[i] = null
      lower[i] = null
      continue
    }
    const slice = closes.slice(i - window + 1, i + 1)
    const m = slice.reduce((a, b) => a + b, 0) / window
    const variance = slice.reduce((a, b) => a + (b - m) ** 2, 0) / window
    const sd = Math.sqrt(variance)
    upper[i] = m + 2 * sd
    lower[i] = m - 2 * sd
  }
  return { mid, upper, lower }
}

const chartOption = computed<EChartsOption>(() => {
  const bars = payload.value?.bars ?? []
  if (bars.length === 0) {
    return {
      backgroundColor: 'transparent',
      title: {
        text: '暂无 K 线',
        left: 'center',
        top: 'middle',
        textStyle: { color: '#7f8ea3', fontSize: 13 },
      },
    }
  }
  const dates = bars.map((b) => b.date)
  const candle = bars.map((b) => [b.open, b.close, b.low, b.high] as [number, number, number, number])
  const vol = bars.map((b) => b.vol)
  const closes = bars.map((b) => b.close)

  // 均线叠加（主图）
  const maSeries = [
    { name: 'MA5', data: smaArr(closes, 5), color: '#f59e0b' },
    { name: 'MA10', data: smaArr(closes, 10), color: '#22d3ee' },
    { name: 'MA20', data: smaArr(closes, 20), color: '#a78bfa' },
    { name: 'MA60', data: smaArr(closes, 60), color: '#f472b6' },
  ]
    .map((s) => ({
      name: s.name,
      type: 'line' as const,
      data: s.data,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 1, color: s.color },
      itemStyle: { color: s.color },
      emphasis: { disabled: true },
    }))

  const hasIndicator = indicator.value !== 'none'
  // 副图：指标区布局（主K线 + 成交量 + 指标）
  const grids = hasIndicator
    ? [
        { left: '8%', right: '4%', top: '10%', height: '42%' },
        { left: '8%', right: '4%', top: '58%', height: '12%' },
        { left: '8%', right: '4%', top: '76%', height: '14%' },
      ]
    : [
        { left: '8%', right: '4%', top: '14%', height: '56%' },
        { left: '8%', right: '4%', top: '76%', height: '14%' },
      ]

  const xAxisCount = hasIndicator ? 3 : 2
  const xAxis: Record<string, unknown>[] = []
  for (let i = 0; i < xAxisCount; i++) {
    xAxis.push({
      type: 'category',
      gridIndex: i,
      data: dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: 'rgba(143, 162, 194, .45)' } },
      axisLabel: i === xAxisCount - 1 ? { color: '#90a2bf', hideOverlap: true } : { show: false },
      splitLine: { show: false },
    })
  }

  const yAxis: Record<string, unknown>[] = [
    {
      scale: true,
      splitArea: { show: true, areaStyle: { color: ['rgba(20,30,50,.35)', 'rgba(10,16,28,.2)'] } },
      axisLabel: { color: '#9ab0ce' },
      splitLine: { lineStyle: { color: 'rgba(103, 126, 162, .22)' } },
    },
    {
      gridIndex: 1,
      splitNumber: 2,
      axisLabel: { color: '#9ab0ce', formatter: (v: number) => (v >= 1e8 ? `${(v / 1e8).toFixed(1)}亿` : `${(v / 1e4).toFixed(0)}万`) },
      axisLine: { lineStyle: { color: 'rgba(143, 162, 194, .45)' } },
      splitLine: { lineStyle: { color: 'rgba(103, 126, 162, .22)' } },
    },
  ]
  if (hasIndicator) {
    yAxis.push({
      gridIndex: 2,
      splitNumber: 2,
      axisLabel: { color: '#9ab0ce' },
      axisLine: { lineStyle: { color: 'rgba(143, 162, 194, .45)' } },
      splitLine: { lineStyle: { color: 'rgba(103, 126, 162, .22)' } },
    })
  }

  const legendData = ['K 线', '成交量', ...maSeries.map((s) => s.name)]
  const series: Record<string, unknown>[] = [
    {
      name: 'K 线',
      type: 'candlestick',
      data: candle,
      itemStyle: {
        color: '#22c55e',
        color0: '#ef4444',
        borderColor: '#22c55e',
        borderColor0: '#ef4444',
      },
    },
    {
      name: '成交量',
      type: 'bar',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: vol,
      itemStyle: { color: 'rgba(90, 169, 255, 0.45)' },
    },
    ...maSeries,
  ]

  // 指标副图系列
  if (indicator.value === 'boll') {
    const b = bollArr(closes, 20)
    legendData.push('BOLL 上', 'BOLL 中', 'BOLL 下')
    series.push(
      { name: 'BOLL 上', type: 'line', data: b.upper, smooth: true, showSymbol: false, lineStyle: { width: 1, color: 'rgba(240,180,41,.6)' }, emphasis: { disabled: true } },
      { name: 'BOLL 中', type: 'line', data: b.mid, smooth: true, showSymbol: false, lineStyle: { width: 1, color: 'rgba(240,180,41,.35)' }, emphasis: { disabled: true } },
      { name: 'BOLL 下', type: 'line', data: b.lower, smooth: true, showSymbol: false, lineStyle: { width: 1, color: 'rgba(240,180,41,.6)' }, emphasis: { disabled: true } },
    )
  } else if (indicator.value === 'macd') {
    const m = macdArr(closes)
    legendData.push('MACD DIF', 'MACD DEA', 'MACD 柱')
    series.push(
      {
        name: 'MACD 柱',
        type: 'bar',
        xAxisIndex: 2,
        yAxisIndex: 2,
        data: m.hist,
        itemStyle: {
          color: (params: { data: number }) => (params.data >= 0 ? 'rgba(34,197,94,.75)' : 'rgba(239,68,68,.75)'),
        },
      },
      { name: 'MACD DIF', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: m.dif, smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#f59e0b' }, emphasis: { disabled: true } },
      { name: 'MACD DEA', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: m.dea, smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#22d3ee' }, emphasis: { disabled: true } },
    )
  }

  return {
    backgroundColor: 'transparent',
    animation: false,
    title: { show: false },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(6, 12, 23, 0.95)',
      borderColor: 'rgba(129, 156, 193, 0.35)',
      textStyle: { color: '#dbe8ff', fontSize: 12 },
    },
    legend: {
      top: 4,
      data: legendData,
      textStyle: { color: '#c7d5ea', fontSize: 11 },
    },
    grid: grids,
    xAxis,
    yAxis,
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2].slice(0, xAxisCount), start: 60, end: 100 },
      { show: true, xAxisIndex: [0, 1, 2].slice(0, xAxisCount), type: 'slider', bottom: 6, height: 18 },
    ],
    series,
  }
})

const minuteOption = computed<EChartsOption>(() => {
  const bars = minutePayload.value?.bars ?? []
  if (bars.length === 0) {
    return {
      backgroundColor: 'transparent',
      title: { text: '暂无分时数据', left: 'center', top: 'middle', textStyle: { color: '#7f8ea3', fontSize: 13 } },
    }
  }
  const times = bars.map((b) => b.datetime.slice(11, 16))
  const closes = bars.map((b) => b.close)
  const vols = bars.map((b) => b.vol)
  const base = closes[0] || 1
  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(6, 12, 23, 0.95)',
      borderColor: 'rgba(129, 156, 193, 0.35)',
      textStyle: { color: '#dbe8ff', fontSize: 12 },
    },
    legend: { top: 4, data: ['分时价', '成交量'], textStyle: { color: '#c7d5ea', fontSize: 12 } },
    grid: [
      { left: '8%', right: '4%', top: '14%', height: '56%' },
      { left: '8%', right: '4%', top: '76%', height: '14%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: times,
        axisLine: { lineStyle: { color: 'rgba(143, 162, 194, .45)' } },
        axisLabel: { color: '#90a2bf', hideOverlap: true },
        splitLine: { show: false },
      },
      { type: 'category', gridIndex: 1, data: times, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    yAxis: [
      {
        scale: true,
        axisLabel: { color: '#9ab0ce', formatter: (v: number) => `${v.toFixed(2)}` },
        splitLine: { lineStyle: { color: 'rgba(103, 126, 162, .22)' } },
      },
      {
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { color: '#9ab0ce', formatter: (v: number) => (v >= 1e8 ? `${(v / 1e8).toFixed(1)}亿` : `${(v / 1e4).toFixed(0)}万`) },
        axisLine: { lineStyle: { color: 'rgba(143, 162, 194, .45)' } },
        splitLine: { lineStyle: { color: 'rgba(103, 126, 162, .22)' } },
      },
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 }],
    series: [
      {
        name: '分时价',
        type: 'line',
        data: closes,
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#5aa9ff', width: 1.6 },
        areaStyle: { color: 'rgba(90, 169, 255, 0.12)' },
        markLine: {
          symbol: 'none',
          data: [{ yAxis: base }],
          lineStyle: { color: 'rgba(240, 180, 41, 0.5)', type: 'dashed' },
        },
      },
      { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: vols, itemStyle: { color: 'rgba(90, 169, 255, 0.45)' } },
    ],
  }
})

async function loadMinute() {
  if (!tsCode.value) return
  minuteLoading.value = true
  try {
    minutePayload.value = await getMarketMinute(tsCode.value, minutePeriod.value, 320)
  } catch (e) {
    minutePayload.value = null
    errorMessage.value = e instanceof Error ? e.message : '分时加载失败'
  } finally {
    minuteLoading.value = false
  }
}

async function switchView(mode: ViewMode) {
  viewMode.value = mode
  if (mode === 'minute' && !minutePayload.value && tsCode.value) {
    await loadMinute()
  }
}

async function loadDaily() {
  if (!tsCode.value) return
  loading.value = true
  errorMessage.value = ''
  infoMessage.value = ''
  try {
    payload.value = await getMarketDaily(tsCode.value, start.value, end.value)
  } catch (e) {
    payload.value = null
    errorMessage.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function handleSync() {
  if (!tsCode.value) return
  syncing.value = true
  errorMessage.value = ''
  infoMessage.value = ''
  try {
    const res = await syncMarketToVnpy(tsCode.value, start.value, end.value)
    infoMessage.value = res.message ?? `已写入 ${res.imported_count ?? 0} 条`
  } catch (e) {
    errorMessage.value = e instanceof Error ? e.message : '同步失败'
  } finally {
    syncing.value = false
  }
}

function openUploadDialog() {
  uploadInput.value?.click()
}

async function onCsvSelected(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.csv')) {
    errorMessage.value = '仅支持 .csv 格式的日线数据文件'
    input.value = ''
    return
  }
  uploading.value = true
  errorMessage.value = ''
  infoMessage.value = ''
  try {
    const res = await uploadCsvToVnpy(file)
    infoMessage.value = res.message ?? `已导入 ${res.imported_count ?? 0} 条日线`
    if (tsCode.value) await loadDaily()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '上传失败'
  } finally {
    uploading.value = false
    input.value = ''
  }
}

function goBacktest() {
  const vs = vtSymbol.value
  if (!vs) {
    errorMessage.value = '缺少 vt_symbol，请先加载 K 线'
    return
  }
  router.push({
    path: '/strategies',
    query: { vtSymbol: vs, start: start.value, end: end.value },
  })
}

function exportDailyCsv() {
  const bars = payload.value?.bars ?? []
  if (!bars.length) {
    errorMessage.value = '无数据可导出'
    return
  }
  downloadCsv(
    `${(payload.value?.ts_code ?? 'daily')}_${start.value}_${end.value}.csv`,
    ['date', 'open', 'high', 'low', 'close', 'vol', 'amount'],
    bars.map((b) => [b.date, b.open, b.high, b.low, b.close, b.vol, b.amount]),
  )
}

function applyRouteCode() {
  const c = route.query.ts_code
  tsCode.value = typeof c === 'string' && c.trim() ? c.trim().toUpperCase() : ''
}

onMounted(() => {
  applyRouteCode()
  void loadDaily()
})

watch(
  () => route.query.ts_code,
  () => {
    applyRouteCode()
    void loadDaily()
  },
)

watch([start, end], () => {
  void loadDaily()
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <p class="crumb">
          <RouterLink to="/market">行情</RouterLink>
          <span aria-hidden="true"> / </span>
          <span class="mono">{{ tsCode || '—' }}</span>
        </p>
        <h1 v-if="payload">{{ payload.ts_code }} · 日线</h1>
        <h1 v-else>股票日线</h1>
        <p v-if="payload?.last" class="sub">
          最新收盘日 {{ payload.last.date }} 收盘
          <strong>{{ payload.last.close?.toFixed(2) }}</strong>
          （展示区间：{{ start }} ~ {{ end }}）
        </p>
      </div>
      <RouterLink to="/market" class="ghost">← 股票列表</RouterLink>
    </header>

    <section class="card">
      <div class="row">
        <label> TuShare 代码 <input v-model.trim="tsCode" class="mono" placeholder="600000.SH" @keyup.enter="loadDaily" /></label>
        <label> 开始 <input v-model="start" type="date" /></label>
        <label> 结束 <input v-model="end" type="date" /></label>
        <button type="button" class="btn secondary" :disabled="loading || !tsCode" @click="loadDaily">刷新 K 线</button>
        <span v-if="loading" class="muted">加载中…</span>
      </div>
      <p v-if="vtSymbol" class="hint mono">vn.py 标的：<b>{{ vtSymbol }}</b>（回测引擎使用此格式）</p>
      <p v-if="errorMessage" class="err">{{ errorMessage }}</p>
      <p v-if="infoMessage" class="ok">{{ infoMessage }}</p>

      <div class="actions">
        <button type="button" class="btn secondary" :disabled="syncing || !tsCode" @click="handleSync">
          <Database class="ic" />
          {{ syncing ? '同步中…' : '同步日线到本地库' }}
        </button>
        <button type="button" class="btn secondary" :disabled="uploading" @click="openUploadDialog">
          <Upload class="ic" />
          {{ uploading ? '导入中…' : '导入 CSV 日线' }}
        </button>
        <input
          ref="uploadInput"
          type="file"
          accept=".csv,text/csv"
          class="hidden-file"
          @change="onCsvSelected"
        />
        <button type="button" class="btn secondary" :disabled="!payload?.bars?.length" @click="exportDailyCsv">
          <Download class="ic" />
          导出 CSV
        </button>
        <button type="button" class="btn primary" @click="goBacktest">
          <LineChart class="ic" />
          去回测（我的策略）
        </button>
      </div>
      <p class="tip">
        请先「同步」再回测，否则本地库可能没有该标的日线数据；也可导入本地 CSV 日线文件（ts_code,trade_date,open,high,low,close,vol,amount）。
      </p>

      <div class="tabs">
        <button
          type="button"
          class="tab"
          :class="{ on: viewMode === 'daily' }"
          @click="switchView('daily')"
        >
          日线 K 线
        </button>
        <button
          type="button"
          class="tab"
          :class="{ on: viewMode === 'minute' }"
          @click="switchView('minute')"
        >
          分时
          <select v-model="minutePeriod" class="period" @click.stop @change="loadMinute">
            <option value="m1">1分</option>
            <option value="m5">5分</option>
            <option value="m15">15分</option>
            <option value="m30">30分</option>
            <option value="m60">60分</option>
          </select>
        </button>
        <span v-if="viewMode === 'minute' && minuteLoading" class="muted">加载中…</span>
      </div>

      <div v-if="viewMode === 'daily'" class="indicator-row">
        <span class="row-label">副图:</span>
        <button
          type="button"
          class="tab"
          :class="{ on: indicator === 'none' }"
          @click="indicator = 'none'"
        >
          无
        </button>
        <button
          type="button"
          class="tab"
          :class="{ on: indicator === 'boll' }"
          @click="indicator = 'boll'"
        >
          BOLL
        </button>
        <button
          type="button"
          class="tab"
          :class="{ on: indicator === 'macd' }"
          @click="indicator = 'macd'"
        >
          MACD
        </button>
        <span class="row-label">均线: MA5 / MA10 / MA20 / MA60（主图叠加）</span>
      </div>

      <div v-if="viewMode === 'daily'" class="chart-wrap">
        <v-chart class="chart" :option="chartOption" autoresize />
      </div>
      <div v-else class="chart-wrap">
        <v-chart class="chart" :option="minuteOption" autoresize />
      </div>
    </section>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 6rem 1rem 2rem;
  max-width: 1100px;
  margin: 0 auto;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 1rem;
}
.crumb {
  margin: 0;
  font-size: 0.78rem;
  color: var(--bq-muted);
}
.crumb a {
  color: #9eb6d8;
  text-decoration: none;
}
.crumb a:hover {
  text-decoration: underline;
}
h1 {
  margin: 0.2rem 0 0;
  font-size: 1.2rem;
  color: var(--bq-text);
}
.sub {
  margin: 0.35rem 0 0;
  font-size: 0.82rem;
  color: var(--bq-muted);
}
.sub strong {
  color: #e8f2ff;
}
.ghost {
  font-size: 0.82rem;
  color: #9eb6d8;
  text-decoration: none;
  border: 1px solid rgba(169, 190, 221, 0.25);
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
}
.card {
  border-radius: 16px;
  padding: 1rem;
  background: linear-gradient(160deg, rgba(18, 27, 49, 0.92), rgba(11, 18, 33, 0.9));
  box-shadow: 0 0 0 1px rgba(138, 158, 191, 0.22) inset, 0 20px 50px rgba(0, 0, 0, 0.45);
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  align-items: flex-end;
}
.row label {
  display: grid;
  gap: 0.25rem;
  font-size: 0.75rem;
  color: var(--bq-muted);
}
.row input {
  border: 1px solid rgba(169, 190, 221, 0.2);
  border-radius: 10px;
  padding: 0.45rem 0.5rem;
  background: rgba(8, 12, 21, 0.72);
  color: var(--bq-text);
}
.muted {
  font-size: 0.78rem;
  color: var(--bq-muted);
}
.hint {
  margin: 0.55rem 0 0;
  font-size: 0.78rem;
  color: #9eb6d8;
}
.err {
  margin: 0.45rem 0 0;
  color: #ff8686;
  font-size: 0.82rem;
}
.ok {
  margin: 0.45rem 0 0;
  color: #66d2a0;
  font-size: 0.82rem;
}
.actions {
  margin-top: 0.75rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}
.hidden-file {
  display: none;
}
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-radius: 999px;
  padding: 0.5rem 0.9rem;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  border: 0;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn.secondary {
  background: rgba(18, 28, 46, 0.85);
  color: #c8d8ef;
  border: 1px solid rgba(169, 190, 221, 0.28);
}
.btn.primary {
  background: linear-gradient(140deg, #f0bf75 0%, #c98f43 100%);
  color: #1a1310;
}
.ic {
  width: 0.95rem;
  height: 0.95rem;
}
.tip {
  margin: 0.45rem 0 0;
  font-size: 0.72rem;
  color: var(--bq-muted);
}
.tabs {
  margin-top: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
}
.indicator-row {
  margin-top: 0.6rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.row-label {
  font-size: 0.76rem;
  color: var(--bq-muted);
}
.tab {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  border: 1px solid rgba(128, 152, 190, 0.25);
  border-radius: 999px;
  padding: 0.32rem 0.8rem;
  font-size: 0.8rem;
  background: transparent;
  color: var(--bq-muted);
  cursor: pointer;
}
.tab.on {
  border-color: var(--bq-accent, #5aa9ff);
  color: var(--bq-text);
  background: rgba(90, 169, 255, 0.1);
}
.period {
  border: 0;
  background: transparent;
  color: inherit;
  font-size: 0.76rem;
  cursor: pointer;
}
.chart-wrap {
  margin-top: 0.85rem;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(128, 152, 190, 0.22);
  padding: 0.35rem;
  background: rgba(10, 17, 30, 0.55);
}
.chart {
  width: 100%;
  height: 420px;
}
</style>
