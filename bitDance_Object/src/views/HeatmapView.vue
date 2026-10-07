<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Flame, RefreshCw, Loader2, Download } from 'lucide-vue-next'
import { runHeatmap, type HeatmapBucket, type HeatmapPayload } from '../services/analytics'
import { downloadCsv } from '../utils/csvExport'

const sample = ref(900)
const loading = ref(false)
const err = ref('')
const data = ref<HeatmapPayload | null>(null)

const BUCKET_COLORS: Record<string, string> = {
  '≤-7%': '#7f1d1d',
  '-7~-4%': '#b91c1c',
  '-4~-2%': '#dc2626',
  '-2~0%': '#f87171',
  '0%': '#64748b',
  '0~2%': '#10b981',
  '2~4%': '#059669',
  '4~7%': '#047857',
  '≥7%': '#065f46',
}

function cellColor(pct: number) {
  if (pct <= -7) return '#7f1d1d'
  if (pct <= -4) return '#b91c1c'
  if (pct <= -2) return '#dc2626'
  if (pct < 0) return '#f87171'
  if (pct === 0) return '#475569'
  if (pct < 2) return '#10b981'
  if (pct < 4) return '#059669'
  if (pct < 7) return '#047857'
  return '#065f46'
}

function textColor(pct: number) {
  return Math.abs(pct) >= 2 ? '#fff' : '#1e293b'
}

async function run() {
  loading.value = true
  err.value = ''
  try {
    data.value = await runHeatmap({ sample: sample.value })
  } catch (e) {
    err.value = e instanceof Error ? e.message : '拉取失败'
    data.value = null
  } finally {
    loading.value = false
  }
}

function fmtPct(pct: number) {
  if (pct === 0) return '0.00'
  return `${pct > 0 ? '+' : ''}${pct.toFixed(2)}`
}

function exportCsv() {
  const items = data.value?.items ?? []
  if (!items.length) return
  downloadCsv(
    `market_heatmap_${new Date().toISOString().slice(0, 10)}.csv`,
    ['ts_code', 'name', 'now', 'change_pct'],
    items.map((it) => [it.ts_code, it.name, it.now, it.pct]),
  )
}

onMounted(() => {
  void run()
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title"><Flame class="ic" /> 全市场涨跌热力图</h1>
        <p class="lead">免费实时快照 · 按涨跌幅渲染市场广度（上涨/下跌/平盘分布）</p>
      </div>
      <div class="head-actions">
        <label class="fld">
          <span>取样（只）</span>
          <select v-model="sample">
            <option :value="300">300</option>
            <option :value="600">600</option>
            <option :value="900">900</option>
            <option :value="1200">1200</option>
          </select>
        </label>
        <button class="btn" :disabled="!data?.items.length" @click="exportCsv">
          <Download class="ic" /> 导出 CSV
        </button>
        <button class="btn primary" :disabled="loading" @click="run">
          <Loader2 v-if="loading" class="ic spin" />
          <RefreshCw v-else class="ic" />
          {{ loading ? '拉取中…' : '刷新' }}
        </button>
      </div>
    </header>

    <section class="panel">
      <p v-if="err" class="err">{{ err }}</p>
      <div v-else-if="data" class="summary">
        <span class="sum up">上涨 <b>{{ data.breadth.up }}</b></span>
        <span class="sum down">下跌 <b>{{ data.breadth.down }}</b></span>
        <span class="sum flat">平盘 <b>{{ data.breadth.flat }}</b></span>
        <span class="sum muted">{{ data.message }}</span>
      </div>

      <div v-if="data?.items.length" class="grid">
        <div
          v-for="(it, i) in data.items"
          :key="i"
          class="cell"
          :style="{ backgroundColor: cellColor(it.pct), color: textColor(it.pct) }"
          :title="`${it.ts_code} ${it.name} ${fmtPct(it.pct)}%`"
        >
          <span class="cell-name">{{ it.name }}</span>
          <span class="cell-pct">{{ fmtPct(it.pct) }}%</span>
        </div>
      </div>
      <p v-else-if="!err && !loading" class="muted-cell">暂无数据，点击「刷新」拉取实时快照。</p>
    </section>

    <section v-if="data" class="panel">
      <h2 class="h2">涨跌幅分布</h2>
      <div class="buckets">
        <div v-for="b in data.buckets" :key="b.label" class="bucket" :style="{ backgroundColor: BUCKET_COLORS[b.label] }">
          <span>{{ b.label }}</span>
          <b>{{ b.count }}</b>
        </div>
      </div>
      <p class="hint">颜色越深红跌幅越大，越深绿涨幅越大（腾讯公开延迟行情，仅供研究演示）。</p>
    </section>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; padding: 5.5rem 1.2rem 4rem; max-width: 1200px; margin: 0 auto; }
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 1.2rem; flex-wrap: wrap; }
.title { display: flex; align-items: center; gap: .5rem; margin: 0; font-size: 1.45rem; color: var(--bq-text); }
.lead { margin: .4rem 0 0; color: var(--bq-muted); font-size: .9rem; }
.head-actions { display: flex; gap: .6rem; align-items: end; }
.fld { display: grid; gap: .25rem; font-size: .78rem; color: var(--bq-muted); }
.fld select { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .45rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); }
.btn { display: inline-flex; align-items: center; gap: .35rem; border: 0; border-radius: 999px; padding: .55rem 1rem; font-size: .85rem; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.ic { width: 1rem; height: 1rem; }
.spin { animation: sp 1s linear infinite; }
@keyframes sp { to { transform: rotate(360deg); } }
.panel { margin-bottom: 1rem; padding: 1rem; border-radius: .9rem; background: var(--bq-bg-elevated); border: 1px solid rgba(255,255,255,.06); }
.err { color: #f87171; font-size: .84rem; }
.summary { display: flex; flex-wrap: wrap; gap: 1rem; font-size: .84rem; margin-bottom: .8rem; }
.sum.up b { color: #4ade80; }
.sum.down b { color: #f87171; }
.sum.flat b { color: var(--bq-muted); }
.sum.muted { color: var(--bq-muted); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 3px; }
.cell { display: flex; flex-direction: column; justify-content: space-between; padding: .35rem .5rem; border-radius: 3px; font-size: .72rem; min-height: 48px; cursor: default; }
.cell-name { font-weight: 600; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.cell-pct { font-family: ui-monospace, monospace; }
.h2 { margin: 0 0 .7rem; font-size: .95rem; color: var(--bq-text); }
.buckets { display: flex; flex-wrap: wrap; gap: .35rem; }
.bucket { display: flex; align-items: center; gap: .5rem; padding: .35rem .7rem; border-radius: .5rem; color: #fff; font-size: .78rem; }
.muted-cell { padding: 1rem 0; text-align: center; color: var(--bq-muted); font-size: .82rem; }
.hint { margin: .6rem 0 0; font-size: .76rem; color: var(--bq-muted); }
</style>