<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Radio, RefreshCw, Wifi, WifiOff, Bell } from 'lucide-vue-next'
import { getRealtime, openRealtimeWs, type RealtimeQuote } from '../services/analytics'

const DEFAULT_WATCH = ['sh600519', 'sh601318', 'sz000858', 'sh600036', 'sz000001', 'sh601166']

const codes = ref<string>(DEFAULT_WATCH.join(','))
const rows = ref<Record<string, RealtimeQuote>>({})
const connected = ref(false)
const updating = ref(false)
const err = ref('')
const lastUpdate = ref('')
let closeFn: (() => void) | null = null

interface AlertRule {
  code: string
  kind: 'below' | 'above'
  value: number
  fired: boolean
}
const alertRules = ref<AlertRule[]>([])
const alertCode = ref('sh600519')
const alertKind = ref<'below' | 'above'>('below')
const alertValue = ref(1000)
const alertMessage = ref('')
const alertCount = ref(0)

function parseCodes() {
  return codes.value
    .split(/[,，\s]+/)
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)
    .slice(0, 60)
}

function num(q: RealtimeQuote, ...keys: string[]): number | null {
  for (const k of keys) {
    const v = Number(q[k])
    if (!Number.isNaN(v)) return v
  }
  return null
}

function nameOf(code: string): string {
  return String(rows.value[code]?.name ?? code)
}

function checkAlerts(items: RealtimeQuote[]) {
  for (const q of items) {
    const code = String(q.code ?? q.symbol ?? '')
    if (!code) continue
    const price = num(q, 'now', '最新价', 'price', 'close')
    if (price === null) continue
    for (const rule of alertRules.value) {
      if (rule.code !== code || rule.fired) continue
      const hit = rule.kind === 'below' ? price <= rule.value : price >= rule.value
      if (!hit) continue
      rule.fired = true
      alertCount.value += 1
      alertMessage.value = `${nameOf(code)} ${rule.kind === 'below' ? '跌破' : '涨超'} ${rule.value}（现价 ${price.toFixed(2)}）`
    }
  }
}

function addAlert() {
  const code = alertCode.value.trim().toLowerCase()
  if (!code || !alertRules.value.some((r) => r.code === code && r.kind === alertKind.value && r.value === alertValue.value)) {
    alertRules.value.push({ code, kind: alertKind.value, value: alertValue.value, fired: false })
  }
}

function removeAlert(i: number) {
  alertRules.value.splice(i, 1)
}

function resetAlerts() {
  alertRules.value.forEach((r) => (r.fired = false))
  alertCount.value = 0
  alertMessage.value = ''
}

function absorb(items: RealtimeQuote[]) {
  for (const q of items) {
    const code = String(q.code ?? q.symbol ?? '')
    if (code) rows.value[code] = q
  }
  checkAlerts(items)
  updating.value = true
  setTimeout(() => (updating.value = false), 200)
  lastUpdate.value = new Date().toLocaleTimeString()
}

async function refreshOnce() {
  const cs = parseCodes()
  if (!cs.length) return
  try {
    const data = await getRealtime(cs)
    absorb(data.items)
    err.value = ''
  } catch (e) {
    err.value = e instanceof Error ? e.message : '拉取失败'
  }
}

function connect() {
  disconnect()
  const cs = parseCodes()
  if (!cs.length) return
  closeFn = openRealtimeWs(cs, (items) => {
    connected.value = true
    absorb(items)
  })
  // 兜底：若 2.5s 内 WS 未送达，用 REST 先拉一次
  setTimeout(() => {
    if (!Object.keys(rows.value).length) void refreshOnce()
  }, 2500)
}

function disconnect() {
  closeFn?.()
  closeFn = null
  connected.value = false
}

function field(q: RealtimeQuote, ...keys: string[]): string {
  for (const k of keys) {
    const v = q[k]
    if (v !== undefined && v !== null && v !== '') return String(v)
  }
  return '—'
}

function changeClass(q: RealtimeQuote) {
  const c = num(q, '涨跌', 'change', 'price_change')
  if (c === null || c === 0) return ''
  return c > 0 ? 'up' : 'down'
}

function changeText(q: RealtimeQuote) {
  const c = num(q, '涨跌', 'change', 'price_change')
  const p = num(q, '涨跌幅', 'change_pct', 'change_percent')
  return `${c !== null ? c.toFixed(2) : '—'} / ${p !== null ? `${p.toFixed(2)}%` : '—'}`
}

onMounted(() => {
  void refreshOnce()
  connect()
})

onUnmounted(disconnect)
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title"><Radio class="ic" /> 实时行情推送</h1>
        <p class="lead">WebSocket 服务端每 3 秒推送腾讯实时快照（WS 不可用时自动降级为 REST 轮询）</p>
      </div>
      <span class="badge" :class="connected ? 'on' : 'off'">
        <Wifi v-if="connected" class="ic" />
        <WifiOff v-else class="ic" />
        {{ connected ? 'WS 已连接' : '轮询模式' }}
      </span>
    </header>

    <section class="panel">
      <div class="controls">
        <label class="fld">
          <span>自选（腾讯代码，逗号分隔）</span>
          <input v-model="codes" placeholder="sh600519,sz000858" />
        </label>
        <button class="btn" @click="refreshOnce">
          <RefreshCw class="ic" :class="{ spin: updating }" /> 立即刷新
        </button>
        <button class="btn primary" @click="connect">重新连接 WS</button>
      </div>
      <p class="hint">支持 sh / sz / bj 前缀，最多 60 只。腾讯接口为延迟行情，仅供研究演示。</p>
      <p v-if="err" class="err">{{ err }}</p>
      <p v-if="lastUpdate" class="ok">最近更新：{{ lastUpdate }}</p>
    </section>

    <section class="panel">
      <h2 class="h2">
        <Bell class="ic" /> 价格预警
        <span v-if="alertCount" class="alert-badge">{{ alertCount }}</span>
      </h2>
      <div class="alert-form">
        <input v-model="alertCode" class="mono" placeholder="sh600519" />
        <select v-model="alertKind">
          <option value="below">跌破</option>
          <option value="above">涨超</option>
        </select>
        <input v-model.number="alertValue" type="number" placeholder="阈值" />
        <button class="btn" @click="addAlert">添加规则</button>
        <button class="btn" @click="resetAlerts">重置触发</button>
      </div>
      <p v-if="alertMessage" class="alert-hit">{{ alertMessage }}</p>
      <ul v-if="alertRules.length" class="alert-list">
        <li v-for="(rule, i) in alertRules" :key="i">
          <span class="mono">{{ rule.code }}</span>
          <span>{{ rule.kind === 'below' ? '跌破' : '涨超' }} {{ rule.value }}</span>
          <span :class="rule.fired ? 'hit' : 'idle'">{{ rule.fired ? '已触发' : '监控中' }}</span>
          <button class="rm" @click="removeAlert(i)">×</button>
        </li>
      </ul>
      <p class="hint">规则在每次行情推送时自动检测，命中即标记（WS 连接期间有效）。</p>
    </section>

    <section class="panel">
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th class="left">代码</th>
              <th class="left">名称</th>
              <th>最新价</th>
              <th>涨跌 / 涨跌幅</th>
              <th>买一</th>
              <th>卖一</th>
              <th>成交量(手)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(q, code) in rows" :key="code">
              <td class="left">{{ code }}</td>
              <td class="left">{{ field(q, 'name', '名称') }}</td>
              <td :class="changeClass(q)">{{ field(q, 'now', '最新价', 'price', 'close') }}</td>
              <td :class="changeClass(q)">{{ changeText(q) }}</td>
              <td>{{ field(q, 'bid', '买一', 'bid_price') }}</td>
              <td>{{ field(q, 'ask', '卖一', 'ask_price') }}</td>
              <td>{{ field(q, 'volume', '成交量') }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="!Object.keys(rows).length" class="muted-cell">暂无数据，点击「立即刷新」或等待推送</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; padding: 5.5rem 1.2rem 4rem; max-width: 1100px; margin: 0 auto; }
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 1.2rem; }
.title { display: flex; align-items: center; gap: .5rem; margin: 0; font-size: 1.45rem; color: var(--bq-text); }
.lead { margin: .4rem 0 0; color: var(--bq-muted); font-size: .9rem; }
.badge { display: inline-flex; align-items: center; gap: .3rem; font-size: .74rem; padding: .3rem .6rem; border-radius: 999px; border: 1px solid rgba(255,255,255,.14); color: var(--bq-muted); white-space: nowrap; }
.badge.on { color: #4ade80; border-color: rgba(74,222,128,.4); }
.panel { margin-bottom: 1rem; padding: 1rem; border-radius: .9rem; background: var(--bq-bg-elevated); border: 1px solid rgba(255,255,255,.06); }
.controls { display: flex; flex-wrap: wrap; gap: .6rem; align-items: end; }
.fld { display: grid; gap: .25rem; font-size: .78rem; color: var(--bq-muted); flex: 1; }
.fld input { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .45rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); }
.btn { display: inline-flex; align-items: center; gap: .35rem; border: 1px solid rgba(255,255,255,.14); border-radius: 999px; padding: .5rem .9rem; font-size: .82rem; background: transparent; color: var(--bq-text); cursor: pointer; }
.btn.primary { background: #2563eb; border-color: transparent; color: #fff; }
.ic { width: 1rem; height: 1rem; }
.spin { animation: sp 1s linear infinite; }
@keyframes sp { to { transform: rotate(360deg); } }
.hint { margin: .6rem 0 0; font-size: .76rem; color: var(--bq-muted); }
.err { margin: .6rem 0 0; color: #f87171; font-size: .82rem; }
.ok { margin: .4rem 0 0; color: #4ade80; font-size: .78rem; }
.table-wrap { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: .84rem; }
.tbl th, .tbl td { padding: .45rem .6rem; border-bottom: 1px solid rgba(255,255,255,.06); color: var(--bq-text); text-align: right; white-space: nowrap; }
.tbl th.left, .tbl td.left { text-align: left; }
.up { color: #ef4444; }
.down { color: #22c55e; }
.muted-cell { padding: 1rem 0; text-align: center; color: var(--bq-muted); font-size: .82rem; }

.h2 { display: flex; align-items: center; gap: .35rem; margin: 0 0 .7rem; font-size: .95rem; color: var(--bq-text); }
.alert-badge { background: #ef4444; color: #fff; border-radius: 999px; font-size: .68rem; padding: .05rem .4rem; }
.alert-form { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
.alert-form input[type="text"], .alert-form input.mono { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .45rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); width: 130px; }
.alert-form input[type="number"] { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .45rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); width: 100px; }
.alert-form select { border: 1px solid rgba(255,255,255,.14); border-radius: .5rem; padding: .45rem .5rem; background: rgba(8,12,21,.7); color: var(--bq-text); }
.mono { font-family: ui-monospace, monospace; }
.alert-hit { margin: .6rem 0 0; color: #f0b429; font-size: .84rem; }
.alert-list { margin: .6rem 0 0; padding: 0; list-style: none; display: grid; gap: .3rem; }
.alert-list li { display: flex; align-items: center; gap: .5rem; font-size: .8rem; color: var(--bq-text); border: 1px solid rgba(255,255,255,.08); border-radius: .5rem; padding: .35rem .6rem; }
.alert-list .mono { color: var(--bq-muted); }
.alert-list .hit { color: #f0b429; margin-left: auto; }
.alert-list .idle { color: var(--bq-muted); margin-left: auto; }
.alert-list .rm { border: 0; background: transparent; color: #f87171; cursor: pointer; font-size: 1rem; }

@media (max-width: 640px) {
  .page { padding: 5rem 0.7rem 2.5rem; }
  .head { flex-direction: column; }
  .controls .btn { flex: 1 1 100%; justify-content: center; }
  .tbl { font-size: .76rem; }
  .tbl th, .tbl td { padding: .35rem .4rem; }
}
</style>