<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Wallet, Play, Loader2, TrendingUp, TrendingDown, Minus } from 'lucide-vue-next'
import { listStrategies, type StrategyListItem } from '../services/backtest'
import { runPaper, type PaperPayload } from '../services/analytics'

const strategies = ref<StrategyListItem[]>([])
const sid = ref('01')
const vtSymbol = ref('600519.SSE')
const lookback = ref(120)
const capital = ref(50000)

const loading = ref(false)
const err = ref('')
const data = ref<PaperPayload | null>(null)

async function run() {
  if (!vtSymbol.value.trim()) {
    err.value = '请填写标的'
    return
  }
  loading.value = true
  err.value = ''
  try {
    data.value = await runPaper({
      strategy_id: sid.value,
      vt_symbol: vtSymbol.value.trim().toUpperCase(),
      lookback: lookback.value,
      capital: capital.value,
    })
  } catch (e) {
    err.value = e instanceof Error ? e.message : '模拟失败'
    data.value = null
  } finally {
    loading.value = false
  }
}

function posBadgeClass(code: number) {
  if (code > 0) return 'long'
  if (code < 0) return 'short'
  return 'flat'
}

function unrealClass(v: number) {
  if (v > 0) return 'profit'
  if (v < 0) return 'loss'
  return 'flat'
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
        <h1 class="title"><Wallet class="ic" /> 纸面交易</h1>
        <p class="lead">用策略信号在最新日线上模拟持仓，看当前该持仓/空仓、浮动盈亏与信号历史</p>
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
          <span>vn.py 标的</span>
          <input v-model="vtSymbol" class="mono" placeholder="600519.SSE" />
        </label>
        <label class="fld">
          <span>回看天数</span>
          <input v-model.number="lookback" type="number" min="30" max="400" />
        </label>
        <label class="fld">
          <span>模拟资金</span>
          <input v-model.number="capital" type="number" min="10000" step="10000" />
        </label>
        <button class="btn primary" :disabled="loading" @click="run">
          <Loader2 v-if="loading" class="ic spin" />
          <Play v-else class="ic" />
          {{ loading ? '模拟中…' : '运行纸面交易' }}
        </button>
      </div>
      <p v-if="err" class="err">{{ err }}</p>
      <p v-else-if="data" class="ok">{{ data.message }}</p>
      <p class="hint">仅为研究演示，不涉及实盘资金。空仓 = 近期无明确方向信号。</p>
    </section>

    <template v-if="data?.success">
      <section class="panel">
        <h2 class="h2">{{ data.vt_symbol }} · {{ data.class_name }}</h2>
        <div class="grid3">
          <div class="stat">
            <span class="stat-label">当前持仓</span>
            <span class="stat-val" :class="posBadgeClass(data.position_code)">
              <TrendingUp v-if="data.position_code > 0" class="ic-xs" />
              <TrendingDown v-else-if="data.position_code < 0" class="ic-xs" />
              <Minus v-else class="ic-xs" />
              {{ data.position }}
            </span>
          </div>
          <div class="stat">
            <span class="stat-label">进场日期 / 成本</span>
            <span class="stat-val">{{ data.entry_date ?? '—' }} @ {{ data.entry_price?.toFixed(2) ?? '—' }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">最新价 / 浮动</span>
            <span class="stat-val" :class="unrealClass(data.unrealized_pct)">
              {{ data.latest_price.toFixed(2) }}（{{ data.unrealized_pct > 0 ? '+' : '' }}{{ data.unrealized_pct.toFixed(2) }}%）
            </span>
          </div>
        </div>
        <p class="hint">策略参数：{{ Object.entries(data.params_used ?? {}).map(([k, v]) => `${k}=${v}`).join(' · ') || '默认' }}</p>
      </section>

      <section class="panel">
        <h2 class="h2">最近信号（{{ data.signals.length }}/{{ data.signal_count }}）</h2>
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th class="left">日期</th>
                <th>信号</th>
                <th>触发价</th>
                <th>方向</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in [...data.signals].reverse()" :key="s.date + s.price">
                <td class="left">{{ s.date }}</td>
                <td>
                  <span :class="s.side === 'buy' ? 'long' : 'short'">{{ s.side === 'buy' ? '做多' : '做空' }}</span>
                </td>
                <td>{{ s.price.toFixed(2) }}</td>
                <td>{{ s.position_after > 0 ? '多' : '空' }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="!data.signals.length" class="muted-cell">暂无信号区间内（可能策略参数与行情不匹配）</p>
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
.btn { display: inline-flex; align-items: center; gap: .35rem; border: 0; border-radius: 999px; padding: .55rem 1rem; font-size: .85rem; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.ic { width: 1rem; height: 1rem; }
.ic-xs { width: .85rem; height: .85rem; }
.spin { animation: sp 1s linear infinite; }
@keyframes sp { to { transform: rotate(360deg); } }
.err { margin: .6rem 0 0; color: #f87171; font-size: .82rem; }
.ok { margin: .6rem 0 0; color: #4ade80; font-size: .82rem; }
.hint { margin: .6rem 0 0; font-size: .76rem; color: var(--bq-muted); }
.mono { font-family: ui-monospace, monospace; }
.h2 { margin: 0 0 .7rem; font-size: .95rem; color: var(--bq-text); }
.grid3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .6rem; }
.stat { display: grid; gap: .25rem; padding: .7rem; border: 1px solid rgba(255,255,255,.08); border-radius: .7rem; }
.stat-label { font-size: .72rem; color: var(--bq-muted); }
.stat-val { display: inline-flex; align-items: center; gap: .3rem; font-size: 1.05rem; font-weight: 700; color: var(--bq-text); }
.stat-val.long { color: #4ade80; }
.stat-val.short { color: #f87171; }
.stat-val.flat { color: var(--bq-muted); }
.stat-val.profit { color: #4ade80; }
.stat-val.loss { color: #f87171; }
.long { color: #4ade80; }
.short { color: #f87171; }
.table-wrap { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: .82rem; }
.tbl th, .tbl td { padding: .45rem .6rem; border-bottom: 1px solid rgba(255,255,255,.06); color: var(--bq-text); text-align: right; white-space: nowrap; }
.tbl th.left, .tbl td.left { text-align: left; }
.muted-cell { padding: 1rem 0; text-align: center; color: var(--bq-muted); font-size: .82rem; }

@media (max-width: 640px) {
  .page { padding: 5rem 0.7rem 2.5rem; }
  .fld { flex: 1 1 100%; }
  .fld input, .fld select { width: 100%; }
  .controls .btn { flex: 1 1 100%; justify-content: center; }
  .tbl { font-size: .74rem; }
}
</style>