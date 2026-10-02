<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { EChartsOption } from 'echarts'
import VChart from 'vue-echarts'
import MarkdownBody from '../components/bitdance/MarkdownBody.vue'
import { Play, Share2 } from 'lucide-vue-next'
import { listStrategies, runBacktest, type BacktestParams, type BacktestResult, type StrategyListItem } from '../services/backtest'
import { formatStrategyOptionLabel } from '../data/strategyDisplayNames'
import { setLastBacktestResult } from '../state/bitdanceBacktestContext'
import { getToken } from '../services/auth'
import {
  buildStrategyShareMarkdown,
  defaultStrategyShareTitle,
  publishStrategyShare,
} from '../services/strategyShare'

const route = useRoute()
const router = useRouter()

const form = ref({
  strategyId: '01',
  vtSymbol: '600031.SSE',
  start: '2024-01-01',
  end: '2026-12-31',
  rate: 0.0003,
  slippage: 0.01,
  size: 1,
  pricetick: 0.01,
  capital: 10_000,
  fastWindow: 3,
  slowWindow: 6,
  signalWindow: 4,
  atrWindow: 6,
  atrMult: 1.2,
  fixedSize: 1000,
})
const loading = ref(false)
const loadingStrategies = ref(false)
const showAdvanced = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const result = ref<BacktestResult | null>(null)
const strategies = ref<StrategyListItem[]>([])
const shareBusy = ref(false)
const shareModalOpen = ref(false)
const shareTitle = ref('')
const shareIntro = ref('')
const perfChartRef = ref<InstanceType<typeof VChart> | null>(null)
const ddChartRef = ref<InstanceType<typeof VChart> | null>(null)

const sharePreviewMarkdown = computed(() => {
  if (!shareModalOpen.value || !result.value) {
    return ''
  }
  const md = buildStrategyShareMarkdown({
    intro: shareIntro.value,
    params: form.value as BacktestParams,
    result: result.value,
    strategyDisplayLine: strategyShareLabel.value,
    seriesTailRows: 40,
  })
  return `${md}\n\n> **预览说明**：确认发布时会把当前页面两张图表以图片形式嵌入正文。`
})

const strategyShareLabel = computed(() => {
  const it = strategies.value.find((x) => x.strategy_id === form.value.strategyId)
  return formatStrategyOptionLabel(
    form.value.strategyId,
    it?.class_name,
    it?.locked,
    it?.archetype,
  )
})

function applyQueryFromRoute() {
  const q = route.query
  if (typeof q.vtSymbol === 'string' && q.vtSymbol.trim()) {
    form.value.vtSymbol = q.vtSymbol.trim()
  }
  if (typeof q.start === 'string' && q.start) {
    form.value.start = q.start
  }
  if (typeof q.end === 'string' && q.end) {
    form.value.end = q.end
  }
}

const metrics = computed(() => {
  const stats = result.value?.stats
  if (!stats) {
    return []
  }
  return [
    { label: '总收益率', value: formatPercent(stats.total_return), hint: '策略区间累计收益' },
    { label: '年化收益', value: formatPercent(stats.annual_return), hint: '折算到年维度的收益率' },
    { label: '夏普比率', value: formatNumber(stats.sharpe_ratio, 3), hint: '单位风险对应超额收益' },
    { label: '最大回撤', value: formatPercent(stats.max_ddpercent), hint: '区间内最大净值回撤' },
    { label: '总成交笔数', value: formatInteger(stats.total_trade_count), hint: '策略总交易次数' },
    { label: '期末权益', value: formatMoney(stats.end_balance), hint: '回测结束账户权益' },
    { label: '净利润', value: formatMoney(stats.total_net_pnl), hint: '总收益扣除成本后结果' },
  ]
})

const performanceChartOption = computed<EChartsOption>(() => {
  const payload = result.value
  const series = payload?.series
  if (!series || series.dates.length === 0) {
    return {
      backgroundColor: 'transparent',
      title: { text: '暂无回测数据', left: 'center', top: 'middle', textStyle: { color: '#7f8ea3', fontSize: 13 } },
    }
  }

  const maxLen = Math.min(
    series.dates.length,
    series.balance.length,
    series.drawdown.length,
  )
  const dates = series.dates.slice(0, maxLen)
  const balance = series.balance.slice(0, maxLen)
  const drawdown = series.drawdown.slice(0, maxLen)
  const benchmark = ((series.benchmark ?? []) as number[]).slice(0, maxLen)
  const tradePoints = payload?.trade_points ?? []
  const baseBalance = balance[0] || 1
  const equityPct = balance.map((v) => ((v - baseBalance) / baseBalance) * 100)
  const benchmarkPct: number[] = benchmark.length ? benchmark : Array.from({ length: maxLen }, () => 0)
  const profitBounds = getAxisBounds([...equityPct, ...benchmarkPct], true)
  const dateToIndex = new Map<string, number>()
  dates.forEach((d, i) => dateToIndex.set(d, i))
  const dayTradeCounter = new Map<string, number>()

  const buyMarkers: Array<{
    value: [string, number]
    tradePrice: number
    tradeVolume: number
    equityPct: number
    tradeAction?: string
    tradeDateTime?: string
  }> = []
  const sellMarkers: Array<{
    value: [string, number]
    tradePrice: number
    tradeVolume: number
    equityPct: number
    tradeAction?: string
    tradeDateTime?: string
  }> = []
  for (const point of tradePoints) {
    const idx = dateToIndex.get(point.date)
    if (idx === undefined) {
      continue
    }
    const count = dayTradeCounter.get(point.date) ?? 0
    dayTradeCounter.set(point.date, count + 1)
    const baseY = equityPct[idx] ?? 0
    const offset = count * 0.25
    const y = point.side === 'buy' ? baseY - offset : baseY + offset
    const marker = {
      value: [point.date, y] as [string, number],
      tradePrice: point.price,
      tradeVolume: point.volume,
      equityPct: baseY,
      tradeAction: point.action,
      tradeDateTime: point.datetime,
    }
    if (point.side === 'buy') buyMarkers.push(marker)
    else sellMarkers.push(marker)
  }

  return {
    backgroundColor: 'transparent',
    title: {
      text: '收益表现（策略 vs 基准）',
      left: 'center',
      top: 4,
      textStyle: { color: '#b2c5e3', fontSize: 13, fontWeight: 600 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(6, 12, 23, 0.95)',
      borderColor: 'rgba(129, 156, 193, 0.35)',
      borderWidth: 1,
      textStyle: { color: '#dbe8ff', fontSize: 12 },
      axisPointer: { type: 'cross', label: { backgroundColor: '#23324a' } },
      formatter: (items: any) => {
        const rows = Array.isArray(items) ? items : [items]
        if (rows.length === 0) {
          return ''
        }
        const date = String(rows[0].axisValue ?? '')
        const lines: string[] = []
        for (const it of rows) {
          if (it.seriesName === '买入点' || it.seriesName === '卖出点') {
            const data = it.data as {
              tradePrice?: number
              tradeVolume?: number
              equityPct?: number
              tradeAction?: string
              tradeDateTime?: string
            } | undefined
            const sideText = it.seriesName === '买入点' ? '买入' : '卖出'
            const actionText = formatTradeAction(data?.tradeAction, sideText)
            const priceText = typeof data?.tradePrice === 'number' ? data.tradePrice.toFixed(2) : '--'
            const volumeText = typeof data?.tradeVolume === 'number' ? data.tradeVolume.toFixed(0) : '--'
            const equityText = typeof data?.equityPct === 'number' ? `${data.equityPct.toFixed(2)}%` : '--'
            const dtText = data?.tradeDateTime ? ` | 成交时间 ${data.tradeDateTime}` : ''
            lines.push(`${it.marker}<b>${actionText}</b> | 价格 ${priceText} | 手数 ${volumeText} | 当日收益率 ${equityText}${dtText}`)
            continue
          }
          const v = Array.isArray(it.value) ? it.value[1] : it.value
          const n = typeof v === 'number' ? `${v.toFixed(2)}%` : String(v)
          lines.push(`${it.marker}${it.seriesName}: <b>${n}</b>`)
        }
        return `${date}<br/>${lines.join('<br/>')}`
      },
    },
    legend: {
      top: 36,
      itemWidth: 10,
      itemHeight: 10,
      data: ['策略收益率(%)', '基准涨跌(%)', '买入点', '卖出点'],
      textStyle: { color: '#c7d5ea', fontSize: 12 },
    },
    grid: { left: 56, right: 24, top: 84, bottom: 52 },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'rgba(143, 162, 194, .45)' } },
      axisTick: { show: false },
      axisLabel: { color: '#90a2bf', showMaxLabel: true, hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      name: '收益率(%)',
      min: profitBounds.min,
      max: profitBounds.max,
      splitNumber: 5,
      axisLabel: { color: '#9ab0ce', formatter: (value: number) => `${value.toFixed(1)}%` },
      axisLine: { lineStyle: { color: 'rgba(143, 162, 194, .45)' } },
      splitLine: { lineStyle: { color: 'rgba(103, 126, 162, .22)' } },
    },
    series: [
      {
        name: '策略收益率(%)',
        type: 'line',
        smooth: 0.15,
        showSymbol: false,
        data: equityPct,
        lineStyle: { width: 2.4, color: '#5aa9ff' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(90, 169, 255, 0.30)' },
              { offset: 1, color: 'rgba(90, 169, 255, 0.02)' },
            ],
          },
        },
      },
      {
        name: '基准涨跌(%)',
        type: 'line',
        smooth: 0.15,
        showSymbol: false,
        data: benchmarkPct,
        lineStyle: { width: 1.8, type: 'dashed', color: '#f8c26a' },
      },
      {
        name: '买入点',
        type: 'scatter',
        symbol: 'triangle',
        symbolRotate: 0,
        symbolSize: 14,
        data: buyMarkers,
        itemStyle: { color: '#22c55e' },
      },
      {
        name: '卖出点',
        type: 'scatter',
        symbol: 'triangle',
        symbolRotate: 180,
        symbolSize: 14,
        data: sellMarkers,
        itemStyle: { color: '#ef4444' },
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        throttle: 60,
      },
      {
        type: 'slider',
        height: 16,
        bottom: 8,
        borderColor: 'rgba(138, 157, 189, .35)',
        backgroundColor: 'rgba(14, 21, 35, .95)',
        fillerColor: 'rgba(91, 162, 255, .22)',
      },
    ],
  }
})

const drawdownChartOption = computed<EChartsOption>(() => {
  const series = result.value?.series
  if (!series || series.dates.length === 0) {
    return {
      backgroundColor: 'transparent',
      title: { text: '暂无回撤数据', left: 'center', top: 'middle', textStyle: { color: '#7f8ea3', fontSize: 13 } },
    }
  }

  const maxLen = Math.min(series.dates.length, series.drawdown.length)
  const dates = series.dates.slice(0, maxLen)
  const balance = series.balance.slice(0, maxLen)
  const drawdownPct = computeDrawdownPct(balance)
  const drawdownBounds = getAxisBounds(drawdownPct, false)
  const minDrawdown = drawdownPct.reduce(
    (acc, value, idx) => (value < acc.value ? { value, idx } : acc),
    { value: Number.POSITIVE_INFINITY, idx: 0 },
  )

  return {
    backgroundColor: 'transparent',
    title: {
      text: '风险表现（回撤曲线）',
      left: 'center',
      top: 4,
      textStyle: { color: '#b2c5e3', fontSize: 13, fontWeight: 600 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(6, 12, 23, 0.95)',
      borderColor: 'rgba(129, 156, 193, 0.35)',
      borderWidth: 1,
      textStyle: { color: '#dbe8ff', fontSize: 12 },
      formatter: (items: any) => {
        const item = Array.isArray(items) ? items[0] : items
        const date = String(item?.axisValue ?? '')
        const value = typeof item?.value === 'number' ? `${item.value.toFixed(2)}%` : '--'
        return `${date}<br/>回撤: <b>${value}</b>`
      },
    },
    grid: { left: 56, right: 24, top: 56, bottom: 32 },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'rgba(143, 162, 194, .45)' } },
      axisTick: { show: false },
      axisLabel: { color: '#90a2bf', showMaxLabel: true, hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      name: '回撤(%)',
      min: drawdownBounds.min,
      max: drawdownBounds.max,
      splitNumber: 4,
      axisLabel: { color: '#9ab0ce', formatter: (value: number) => `${value.toFixed(1)}%` },
      axisLine: { lineStyle: { color: 'rgba(143, 162, 194, .45)' } },
      splitLine: { lineStyle: { color: 'rgba(103, 126, 162, .22)' } },
    },
    series: [
      {
        name: '回撤(%)',
        type: 'line',
        smooth: 0.15,
        showSymbol: false,
        data: drawdownPct,
        lineStyle: { width: 2, color: '#f97373' },
        areaStyle: { color: 'rgba(249, 115, 115, 0.18)' },
        markPoint: {
          symbolSize: 38,
          label: { color: '#fff', formatter: '最大回撤' },
          data: [{ name: '最大回撤', coord: [dates[minDrawdown.idx], minDrawdown.value], value: minDrawdown.value }],
        },
      },
    ],
  }
})

async function loadStrategies() {
  loadingStrategies.value = true
  try {
    const items = await listStrategies()
    strategies.value = items
    if (items.length === 0) return
    const sel = form.value.strategyId
    const selItem = items.find((it) => it.strategy_id === sel)
    if (!selItem || selItem.locked) {
      const firstFree = items.find((it) => !it.locked) ?? items[0]
      form.value.strategyId = firstFree.strategy_id
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '策略列表加载失败'
  } finally {
    loadingStrategies.value = false
  }
}

async function handleRunBacktest() {
  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const data = await runBacktest(form.value)
    result.value = data
    setLastBacktestResult(data)
    if (data.success) {
      successMessage.value = `回测成功，参数已生效：${JSON.stringify(data.params)}`
    } else {
      successMessage.value = `参数已生效：${JSON.stringify(data.params)}`
      errorMessage.value = data.message
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '回测请求失败'
  } finally {
    loading.value = false
  }
}

function openShareModal() {
  if (!result.value) {
    errorMessage.value = '请先运行一次回测后再分享到社区'
    return
  }
  if (!getToken()) {
    router.push({ path: '/login', query: { redirect: '/strategies' } })
    return
  }
  shareTitle.value = defaultStrategyShareTitle(form.value as BacktestParams)
  shareIntro.value = ''
  shareModalOpen.value = true
}

function closeShareModal() {
  shareModalOpen.value = false
}

function raf2(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve())
    })
  })
}

/** 确保 ECharts 完成布局后再导出，避免拿到旧帧或裁切不完整的位图 */
async function prepareChartsForSnapshot() {
  await nextTick()
  await raf2()
  perfChartRef.value?.resize?.()
  ddChartRef.value?.resize?.()
  await raf2()
  await new Promise<void>((r) => setTimeout(r, 120))
}

function chartDataUrl(inst: InstanceType<typeof VChart> | null): string | undefined {
  if (!inst?.getDataURL) {
    return undefined
  }
  try {
    const u = inst.getDataURL({
      type: 'jpeg',
      pixelRatio: 0.72,
      backgroundColor: 'rgba(11, 18, 33, 0.98)',
      /** 静态图不需要缩放条；去掉后画布会为绘图区让出底部空间，避免与图例/标题抢位 */
      excludeComponents: ['dataZoom'],
    })
    const t = u?.trim()
    return t && t.startsWith('data:') ? t : undefined
  } catch {
    return undefined
  }
}

async function confirmPublishShare() {
  if (!result.value) {
    return
  }
  shareBusy.value = true
  errorMessage.value = ''
  try {
    await prepareChartsForSnapshot()
    const performanceUrl = chartDataUrl(perfChartRef.value)
    const drawdownUrl = chartDataUrl(ddChartRef.value)
    const post = await publishStrategyShare({
      title: shareTitle.value,
      intro: shareIntro.value,
      params: form.value as BacktestParams,
      result: result.value,
      strategyDisplayLine: strategyShareLabel.value,
      chartUrls: { performance: performanceUrl, drawdown: drawdownUrl },
      seriesTailRows: 40,
    })
    shareModalOpen.value = false
    await router.push(`/community/post/${post.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '分享到社区失败'
  } finally {
    shareBusy.value = false
  }
}

watch(
  () => route.fullPath,
  () => {
    applyQueryFromRoute()
  },
)

onMounted(() => {
  applyQueryFromRoute()
  loadStrategies()
})

function getAxisBounds(values: number[], includeZero: boolean) {
  const valid = values.filter((v) => Number.isFinite(v))
  if (valid.length === 0) {
    return includeZero ? { min: -1, max: 1 } : { min: -1, max: 0 }
  }

  let min = Math.min(...valid)
  let max = Math.max(...valid)
  if (includeZero) {
    min = Math.min(min, 0)
    max = Math.max(max, 0)
  }

  if (min === max) {
    const delta = Math.abs(min) < 1 ? 1 : Math.abs(min) * 0.2
    return { min: min - delta, max: max + delta }
  }

  const range = max - min
  const padding = Math.max(range * 0.15, 0.2)
  return { min: min - padding, max: max + padding }
}

function computeDrawdownPct(balance: number[]) {
  const output: number[] = []
  let peak = Number.NEGATIVE_INFINITY
  for (const value of balance) {
    const current = Number.isFinite(value) ? value : 0
    peak = Math.max(peak, current)
    if (peak <= 0) {
      output.push(0)
      continue
    }
    output.push(((current / peak) - 1) * 100)
  }
  return output
}

function formatPercent(value?: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--'
  }
  return `${value.toFixed(2)}%`
}

function formatNumber(value?: number, digits = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--'
  }
  return value.toFixed(digits)
}

function formatInteger(value?: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--'
  }
  return value.toLocaleString()
}

function formatMoney(value?: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--'
  }
  return `¥${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

function formatTradeAction(action: string | undefined, fallbackSide: string) {
  if (action === 'buy_open') return '开多(买入)'
  if (action === 'buy_close') return '平空(买入)'
  if (action === 'sell_open') return '开空(卖出)'
  if (action === 'sell_close') return '平多(卖出)'
  return fallbackSide
}
</script>

<template>
  <div class="page">
    <section class="card">
      <h2>策略回测</h2>
      <div class="form-grid">
        <label>
          策略
          <select v-model="form.strategyId" :disabled="loadingStrategies || strategies.length === 0">
            <option
              v-for="it in strategies"
              :key="it.strategy_id"
              :value="it.strategy_id"
              :disabled="Boolean(it.locked)"
              :title="formatStrategyOptionLabel(it.strategy_id, it.class_name, it.locked, it.archetype)"
            >
              {{ formatStrategyOptionLabel(it.strategy_id, it.class_name, it.locked, it.archetype) }}
            </option>
          </select>
        </label>
        <p class="tier-hint">
          非会员仅可使用列表中的第一个策略；开通会员可解锁其余策略与 AI 问答。
        </p>
        <p class="tier-hint archetype-hint">
          99 份聚宽模板已<strong>去重改写</strong>为 23 类 vn.py 策略族（如「双均线金叉模版」），
          同一族共享一套信号逻辑，不同策略仅参数不同；同参数下<strong>回测曲线一致</strong>。
          若需区分收益，请选不同模版或调整参数。
        </p>
        <label>标的<input v-model.trim="form.vtSymbol" placeholder="如 600031.SSE" /></label>
        <label>开始日期<input v-model="form.start" type="date" /></label>
        <label>结束日期<input v-model="form.end" type="date" /></label>
      </div>
      <button type="button" class="secondary-btn" @click="showAdvanced = !showAdvanced">
        {{ showAdvanced ? '收起高级参数' : '展开高级参数' }}
      </button>
      <div v-if="showAdvanced" class="form-grid advanced-grid">
        <label>手续费率 rate<input v-model.number="form.rate" type="number" step="0.0001" min="0" /></label>
        <label>滑点 slippage<input v-model.number="form.slippage" type="number" step="0.001" min="0" /></label>
        <label>合约乘数 size<input v-model.number="form.size" type="number" step="0.1" min="0.0001" /></label>
        <label>最小价格跳动 pricetick<input v-model.number="form.pricetick" type="number" step="0.0001" min="0.0001" /></label>
        <label>初始资金 capital<input v-model.number="form.capital" type="number" step="1000" min="1" /></label>
        <label>快线窗口 fastWindow<input v-model.number="form.fastWindow" type="number" step="1" min="1" /></label>
        <label>慢线窗口 slowWindow<input v-model.number="form.slowWindow" type="number" step="1" min="1" /></label>
        <label>信号窗口 signalWindow<input v-model.number="form.signalWindow" type="number" step="1" min="1" /></label>
        <label>ATR窗口 atrWindow<input v-model.number="form.atrWindow" type="number" step="1" min="1" /></label>
        <label>ATR倍数 atrMult<input v-model.number="form.atrMult" type="number" step="0.1" min="0" /></label>
        <label>每次下单手数 fixedSize<input v-model.number="form.fixedSize" type="number" step="1" min="1" /></label>
      </div>
      <div class="run-actions">
        <button type="button" class="run-btn" :disabled="loading" @click="handleRunBacktest">
          <Play class="ic" />
          {{ loading ? '回测中...' : '运行回测' }}
        </button>
        <button
          type="button"
          class="share-btn"
          :disabled="shareBusy || !result"
          :title="!result ? '请先完成一次回测' : '将当前参数与回测摘要发布为社区帖子'"
          @click="openShareModal"
        >
          <Share2 class="ic" />
          {{ shareBusy ? '发布中…' : '一键分享到社区' }}
        </button>
      </div>
      <p v-if="errorMessage" class="err">{{ errorMessage }}</p>
      <p v-if="successMessage" class="ok-msg">{{ successMessage }}</p>

      <div v-if="result" class="result">
        <div v-for="metric in metrics" :key="metric.label" class="metric">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <small>{{ metric.hint }}</small>
        </div>
      </div>

      <div class="chart-wrap">
        <VChart ref="perfChartRef" class="chart chart-main" :option="performanceChartOption" autoresize />
      </div>
      <div class="chart-wrap">
        <VChart ref="ddChartRef" class="chart chart-sub" :option="drawdownChartOption" autoresize />
      </div>
    </section>

    <Teleport to="body">
      <div
        v-if="shareModalOpen"
        class="share-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="share-dialog-title"
        @click.self="closeShareModal"
      >
        <div class="share-dialog">
          <h3 id="share-dialog-title" class="share-dlg-title">分享到社区</h3>
          <p class="share-dlg-hint">
            将回测参数、策略说明、绩效与数据表发布为帖子；确认时从当前页面导出两张图（无 dataZoom 滑条，含图内标题）。
            若社区里仍是旧图，请<strong>重新发布</strong>一条帖子以生成新图。
          </p>
          <label class="share-field">
            <span>标题</span>
            <input v-model="shareTitle" type="text" maxlength="200" placeholder="自定义帖子标题" />
          </label>
          <label class="share-field">
            <span>简介（可选）</span>
            <textarea v-model="shareIntro" rows="4" placeholder="思路简述、风险提示等（支持 Markdown）" />
          </label>
          <div class="share-field">
            <span>正文预览</span>
            <div class="share-preview">
              <MarkdownBody :source="sharePreviewMarkdown" />
            </div>
          </div>
          <div class="share-actions">
            <button type="button" class="share-cancel" :disabled="shareBusy" @click="closeShareModal">取消</button>
            <button type="button" class="share-confirm" :disabled="shareBusy" @click="confirmPublishShare">
              {{ shareBusy ? '发布中…' : '确认发布' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; padding: 6rem 1rem 2rem; display: grid; place-items: start center; }
.card { width: min(1080px, 100%); border-radius: 16px; padding: 1.05rem; background: radial-gradient(1200px 600px at -10% -20%, rgba(68,112,180,.24), transparent 55%), linear-gradient(160deg, rgba(18,27,49,.92), rgba(11,18,33,.9)); box-shadow: 0 0 0 1px rgba(138, 158, 191, .22) inset, 0 20px 50px rgba(0,0,0,.45); }
.card h2 { margin: 0 0 .8rem; font-size: 1rem; color: var(--bq-text); }
.tier-hint { grid-column: 1 / -1; margin: 0; font-size: .72rem; color: var(--bq-muted); line-height: 1.45; }
.archetype-hint { margin-top: .35rem; }
.form-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .6rem; }
.form-grid label { display: grid; gap: .3rem; font-size: .78rem; color: var(--bq-muted); }
.form-grid input,.form-grid select { border: 1px solid rgba(169,190,221,.2); border-radius: 10px; padding: .5rem .55rem; background: rgba(8,12,21,.72); color: var(--bq-text); }
.run-actions { margin-top: .8rem; display: flex; flex-wrap: wrap; gap: .55rem; align-items: center; }
.share-btn {
  border: 1px solid rgba(169, 190, 221, 0.35);
  border-radius: 999px;
  padding: .6rem 1.05rem;
  display: inline-flex;
  align-items: center;
  gap: .35rem;
  cursor: pointer;
  font-weight: 600;
  font-size: .82rem;
  background: rgba(18, 28, 46, 0.75);
  color: #dbe8ff;
  transition: border-color .15s ease, transform .15s ease;
}
.share-btn:hover:not(:disabled) {
  border-color: rgba(129, 168, 220, 0.55);
  transform: translateY(-1px);
}
.share-btn:disabled {
  opacity: .45;
  cursor: not-allowed;
  transform: none;
}
.run-btn { margin-top: 0; border: 0; border-radius: 999px; padding: .6rem 1.05rem; display: inline-flex; align-items: center; gap: .35rem; cursor: pointer; font-weight: 700; background: linear-gradient(140deg, #f0bf75 0%, #c98f43 100%); color: #1a1310; box-shadow: 0 8px 24px rgba(230, 168, 85, .25); transition: transform .15s ease, box-shadow .2s ease; }
.run-btn:hover { transform: translateY(-1px); box-shadow: 0 10px 28px rgba(230, 168, 85, .35); }
.run-btn:disabled { cursor: not-allowed; opacity: .72; transform: none; box-shadow: none; }
.secondary-btn { margin-top: .6rem; border: 1px solid rgba(169,190,221,.25); border-radius: 999px; padding: .45rem .9rem; background: rgba(18,28,46,.6); color: #c8d8ef; cursor: pointer; font-size: .78rem; }
.secondary-btn:hover { border-color: rgba(169,190,221,.4); }
.advanced-grid { margin-top: .6rem; }
.ic { width: .92rem; height: .92rem; }
.err { margin: .55rem 0 0; color: #ff8686; font-size: .8rem; }
.ok-msg { margin: .55rem 0 0; color: #66d2a0; font-size: .8rem; word-break: break-word; }
.result { margin-top: .9rem; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .55rem; }
.metric { display: grid; gap: .3rem; padding: .55rem .65rem; border-radius: 10px; background: linear-gradient(165deg, rgba(15, 25, 42, .86), rgba(11, 19, 33, .82)); border: 1px solid rgba(136, 159, 197, .18); }
.metric span { font-size: .72rem; color: #9eb1cb; }
.metric strong { font-size: .92rem; color: #e8f2ff; font-weight: 700; }
.metric small { font-size: .68rem; color: #7f96b8; line-height: 1.25; }
.chart-wrap { margin-top: .9rem; border-radius: 12px; overflow: hidden; background: linear-gradient(165deg, rgba(10, 17, 30, .88), rgba(6, 11, 21, .9)); border: 1px solid rgba(128, 152, 190, .22); padding: .35rem .45rem .15rem; }
.chart { width: 100%; }
.chart-main { height: 360px; }
.chart-sub { height: 240px; }
@media (max-width: 900px) {
  .form-grid { grid-template-columns: 1fr 1fr; }
  .result { grid-template-columns: 1fr 1fr; }
  .chart-main { height: 280px; }
  .chart-sub { height: 200px; }
}

.share-overlay {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: rgba(4, 8, 16, 0.72);
  backdrop-filter: blur(6px);
}
.share-dialog {
  width: min(640px, 100%);
  max-height: min(90vh, 720px);
  overflow: auto;
  border-radius: 16px;
  padding: 1.1rem 1.15rem;
  background: linear-gradient(165deg, rgba(18, 27, 49, 0.96), rgba(11, 18, 33, 0.94));
  box-shadow:
    0 0 0 1px rgba(138, 158, 191, 0.28) inset,
    0 24px 60px rgba(0, 0, 0, 0.55);
}
.share-dlg-title {
  margin: 0 0 0.35rem;
  font-size: 1.05rem;
  color: var(--bq-text);
}
.share-dlg-hint {
  margin: 0 0 0.85rem;
  font-size: 0.78rem;
  color: var(--bq-muted);
  line-height: 1.45;
}
.share-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.75rem;
  font-size: 0.8rem;
  color: var(--bq-muted);
}
.share-field input,
.share-field textarea {
  border: 1px solid rgba(169, 190, 221, 0.22);
  border-radius: 10px;
  padding: 0.5rem 0.55rem;
  background: rgba(8, 12, 21, 0.72);
  color: var(--bq-text);
  font-size: 0.88rem;
  resize: vertical;
}
.share-preview {
  max-height: 220px;
  overflow: auto;
  border-radius: 10px;
  padding: 0.45rem 0.55rem;
  background: rgba(6, 10, 18, 0.65);
  border: 1px solid rgba(128, 152, 190, 0.18);
}
.share-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.55rem;
  margin-top: 0.35rem;
}
.share-cancel {
  border: 1px solid rgba(169, 190, 221, 0.35);
  border-radius: 10px;
  padding: 0.5rem 0.85rem;
  background: transparent;
  color: var(--bq-muted);
  cursor: pointer;
  font-size: 0.82rem;
}
.share-cancel:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.share-confirm {
  border: 0;
  border-radius: 10px;
  padding: 0.5rem 1rem;
  font-weight: 600;
  font-size: 0.82rem;
  cursor: pointer;
  color: #0d0b07;
  background: linear-gradient(140deg, #f0bf75 0%, #c98f43 100%);
}
.share-confirm:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
