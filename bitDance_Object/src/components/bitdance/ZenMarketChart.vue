<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsOption } from 'echarts'
import VChart from 'vue-echarts'

function buildCandles(n: number) {
  let p = 100
  const data: [number, number, number, number][] = []
  for (let i = 0; i < n; i += 1) {
    const o = p
    const c = p + (Math.random() - 0.48) * 3.2
    const h = Math.max(o, c) + Math.random() * 1.2
    const l = Math.min(o, c) - Math.random() * 1.2
    data.push([o, c, l, h])
    p = c
  }
  return data
}

const candles = buildCandles(42)

const buyIdx = [6, 14, 28]
const sellIdx = [10, 22, 34]

const categories = candles.map((_, i) => `${i + 1}`)

const option = computed<EChartsOption>(() => ({
  backgroundColor: 'transparent',
  silent: true,
  animation: true,
  animationDuration: 900,
  grid: { left: 12, right: 12, top: 28, bottom: 12 },
  tooltip: { show: false },
  axisPointer: { show: false },
  xAxis: {
    type: 'category',
    data: categories,
    show: false,
  },
  yAxis: {
    type: 'value',
    scale: true,
    show: false,
    splitLine: { show: false },
  },
  series: [
    {
      type: 'candlestick',
      silent: true,
      data: candles.map((d) => [d[0], d[1], d[2], d[3]]),
      itemStyle: {
        color: 'rgba(191, 147, 83, 0.92)',
        color0: 'rgba(245, 245, 244, 0.22)',
        borderColor: 'rgba(191, 147, 83, 0.85)',
        borderColor0: 'rgba(245, 245, 244, 0.35)',
      },
      emphasis: { disabled: true },
    },
    {
      type: 'scatter',
      silent: true,
      data: buyIdx.map((i) => [`${i + 1}`, candles[i]?.[1] ?? 0]),
      symbolSize: 10,
      itemStyle: {
        color: 'rgba(191, 147, 83, 0.95)',
        shadowBlur: 14,
        shadowColor: 'rgba(191, 147, 83, 0.45)',
      },
      emphasis: { disabled: true },
    },
    {
      type: 'scatter',
      silent: true,
      data: sellIdx.map((i) => [`${i + 1}`, candles[i]?.[1] ?? 0]),
      symbol: 'circle',
      symbolSize: 11,
      itemStyle: {
        color: 'transparent',
        borderColor: 'rgba(250, 250, 249, 0.88)',
        borderWidth: 1.5,
      },
      emphasis: { disabled: true },
    },
  ],
}))
</script>

<template>
  <section id="chart" class="zen" aria-labelledby="zen-title">
    <div class="zen-head">
      <h2 id="zen-title" class="zen-title">禅意图表</h2>
      <p class="zen-copy">无坐标网格；信号以点阵呈现——金点注入，白环撤离。</p>
    </div>
    <div class="chart-slab">
      <v-chart class="chart" :option="option" autoresize />
    </div>
  </section>
</template>

<style scoped>
.zen {
  margin-top: 3rem;
  scroll-margin-top: 6rem;
}

.zen-head {
  margin-bottom: 1rem;
  max-width: 32rem;
}

.zen-title {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: rgba(191, 147, 83, 0.5);
}

.zen-copy {
  margin: 0.45rem 0 0;
  font-size: 0.875rem;
  line-height: 1.55;
  color: rgba(168, 162, 158, 0.72);
}

.chart-slab {
  position: relative;
  border-radius: 1.25rem;
  padding: 0.5rem 0.25rem 0.25rem;
  min-height: 260px;
  background: radial-gradient(ellipse 80% 70% at 50% 0%, rgba(191, 147, 83, 0.06) 0%, transparent 55%),
    #040404;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.03) inset,
    0 -1px 0 0 rgba(191, 147, 83, 0.08) inset,
    0 32px 64px rgba(0, 0, 0, 0.55),
    -1px -1px 0 0 rgba(191, 147, 83, 0.1);
}

.chart {
  height: 240px;
  width: 100%;
}
</style>

