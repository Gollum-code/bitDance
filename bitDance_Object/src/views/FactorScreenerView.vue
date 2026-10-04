<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { BarChart3, Play, Loader2, ExternalLink } from 'lucide-vue-next'
import { runScreen, type ScreenItem, type ScreenPayload } from '../services/analytics'

const router = useRouter()

const universe = ref(120)
const topN = ref(20)
const lookback = ref(120)
const loading = ref(false)
const err = ref('')
const data = ref<ScreenPayload | null>(null)

async function run() {
  loading.value = true
  err.value = ''
  try {
    data.value = await runScreen({
      universe_limit: universe.value,
      top_n: topN.value,
      lookback_days: lookback.value,
    })
  } catch (e) {
    err.value = e instanceof Error ? e.message : '选股失败'
    data.value = null
  } finally {
    loading.value = false
  }
}

function fmtPct(v: number | undefined) {
  if (v === undefined || Number.isNaN(v)) return '—'
  return `${v.toFixed(2)}%`
}

function fmtRatio(v: number | undefined) {
  if (v === undefined || Number.isNaN(v)) return '—'
  return v.toFixed(2)
}

function scoreColor(score: number) {
  if (score >= 80) return '#4ade80'
  if (score >= 65) return '#f0b429'
  return '#f87171'
}

function openChart(item: ScreenItem) {
  void router.push({ path: '/stock', query: { ts_code: item.ts_code } })
}

onMounted(() => {
  void run()
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title"><BarChart3 class="ic" /> 因子选股器</h1>
        <p class="lead">免费全市场行情 · 动量/趋势/波动/量能/回撤多因子横截面打分 · Top N</p>
      </div>
    </header>

    <section class="panel">
      <div class="controls">
        <label class="fld">
          <span>采样规模（只）</span>
          <input v-model.number="universe" type="number" min="20" max="300" />
        </label>
        <label class="fld">
          <span>Top N</span>
          <input v-model.number="topN" type="number" min="5" max="50" />
        </label>
        <label class="fld">
          <span>回看天数</span>
          <input v-model.number="lookback" type="number" min="40" max="250" />
        </label>
        <button class="btn primary" :disabled="loading" @click="run">
          <Loader2 v-if="loading" class="ic spin" />
          <Play v-else class="ic" />
          {{ loading ? '打分中…' : '开始选股' }}
        </button>
      </div>
      <p v-if="err" class="err">{{ err }}</p>
      <p v-else-if="data" class="ok">{{ data.message }}</p>
      <p v-if="data?.success" class="hint">
        因子：动量 25% · 中期趋势 20% · 波动(反向) 15% · 距高点回撤(反向) 10% · 量能 10% · 均线交叉 10% · 流动性(反向) 10%
      </p>
    </section>

    <section v-if="data?.success" class="panel">
      <h2 class="h2">Top {{ data.items.length }}</h2>
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>排名</th>
              <th class="left">代码 / 名称</th>
              <th>现价</th>
              <th>综合分</th>
              <th>动量</th>
              <th>趋势</th>
              <th>波动率</th>
              <th>量能比</th>
              <th>距高点</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, i) in data.items" :key="item.ts_code">
              <td>{{ i + 1 }}</td>
              <td class="left">
                <b>{{ item.ts_code }}</b>
                <span class="nm">{{ item.name }}</span>
              </td>
              <td>{{ item.close.toFixed(2) }}</td>
              <td>
                <span class="score" :style="{ color: scoreColor(item.score) }">{{ item.score.toFixed(1) }}</span>
              </td>
              <td>{{ fmtPct(item.factors.mom) }}</td>
              <td>{{ fmtPct(item.factors.trend) }}</td>
              <td>{{ fmtPct(item.factors.volatility) }}</td>
              <td>{{ fmtRatio(item.factors.vol_ratio) }}</td>
              <td>{{ fmtPct(item.factors.drawdown_from_high) }}</td>
              <td>
                <button class="link" title="查看 K 线" @click="openChart(item)">
                  <ExternalLink class="ic" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="tip">点击行末图标可跳转到个股日线页回测该标的。打分仅做研究展示，不构成投资建议。</p>
    </section>
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
.fld input { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .45rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); width: 90px; }
.btn { display: inline-flex; align-items: center; gap: .35rem; border: 0; border-radius: 999px; padding: .55rem 1rem; font-size: .85rem; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.ic { width: 1rem; height: 1rem; }
.spin { animation: sp 1s linear infinite; }
@keyframes sp { to { transform: rotate(360deg); } }
.err { margin: .6rem 0 0; color: #f87171; font-size: .82rem; }
.ok { margin: .6rem 0 0; color: #4ade80; font-size: .82rem; }
.hint { margin: .6rem 0 0; font-size: .76rem; color: var(--bq-muted); }
.h2 { margin: 0 0 .7rem; font-size: .95rem; color: var(--bq-text); }
.table-wrap { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: .82rem; }
.tbl th, .tbl td { padding: .45rem .6rem; border-bottom: 1px solid rgba(255,255,255,.06); color: var(--bq-text); text-align: right; white-space: nowrap; }
.tbl th.left, .tbl td.left { text-align: left; }
.nm { margin-left: .35rem; color: var(--bq-muted); }
.score { font-weight: 700; }
.link { border: 0; background: transparent; color: var(--bq-accent); cursor: pointer; display: inline-flex; }
.tip { margin: .7rem 0 0; font-size: .74rem; color: var(--bq-muted); }
</style>