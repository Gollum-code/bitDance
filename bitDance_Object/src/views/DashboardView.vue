<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import {
  getMarketDaily,
  listMarketStocks,
  type DailyBar,
  type StockBasicItem,
} from '../services/market'

const loading = ref(true)
const errorText = ref('')
const keyword = ref('')

// 股票池：沪深 300 蓝筹 + 热门成长
const watchlist = [
  '600519.SH',
  '601318.SH',
  '600036.SH',
  '000858.SZ',
  '000001.SZ',
  '300750.SZ',
  '002594.SZ',
  '600900.SH',
  '601899.SH',
  '000333.SZ',
  '600030.SH',
  '601888.SH',
]

const stockNames: Record<string, string> = {
  '600519.SH': '贵州茅台',
  '601318.SH': '中国平安',
  '600036.SH': '招商银行',
  '000858.SZ': '五粮液',
  '000001.SZ': '平安银行',
  '300750.SZ': '宁德时代',
  '002594.SZ': '比亚迪',
  '600900.SH': '长江电力',
  '601899.SH': '紫金矿业',
  '000333.SZ': '美的集团',
  '600030.SH': '中信证券',
  '601888.SH': '中国中免',
}

type WatchQuote = {
  code: string
  name: string
  vtSymbol: string
  last: number
  pct: number
  change: number
  vol: number
  amount: number
}

const quotes = ref<WatchQuote[]>([])
const searchItems = ref<StockBasicItem[]>([])
const searching = ref(false)
const searchErr = ref('')

async function loadQuotes() {
  const rows: WatchQuote[] = []
  for (const code of watchlist) {
    try {
      const today = new Date()
      const end = today.toISOString().slice(0, 10)
      const start = new Date(today.getTime() - 90 * 86400000).toISOString().slice(0, 10)
      const d = await getMarketDaily(code, start, end)
      const bars: DailyBar[] = d.bars ?? []
      if (!bars.length) continue
      const last = bars[bars.length - 1]
      const prev = bars.length > 1 ? bars[bars.length - 2] : last
      const prevClose = prev?.close ?? last.close
      const pct = prevClose ? ((last.close - prevClose) / prevClose) * 100 : 0
      rows.push({
        code,
        name: stockNames[code] ?? code,
        vtSymbol: d.vt_symbol ?? '',
        last: last.close,
        pct,
        change: last.close - prevClose,
        vol: last.vol,
        amount: last.amount,
      })
    } catch {
      /* skip */
    }
  }
  quotes.value = rows
}

async function doSearch() {
  const q = keyword.value.trim()
  if (!q) {
    searchItems.value = []
    return
  }
  searching.value = true
  searchErr.value = ''
  try {
    const r = await listMarketStocks(q, 20)
    searchItems.value = r.items ?? []
  } catch (e) {
    searchErr.value = e instanceof Error ? e.message : '搜索失败'
  } finally {
    searching.value = false
  }
}

const topGainers = computed(() =>
  [...quotes.value].filter((q) => q.pct >= 0).sort((a, b) => b.pct - a.pct).slice(0, 3),
)
const topLosers = computed(() =>
  [...quotes.value].filter((q) => q.pct < 0).sort((a, b) => a.pct - b.pct).slice(0, 3),
)

const marketAvg = computed(() => {
  if (!quotes.value.length) return 0
  return quotes.value.reduce((s, q) => s + q.pct, 0) / quotes.value.length
})

onMounted(async () => {
  loading.value = true
  await loadQuotes()
  loading.value = false
})
</script>

<template>
  <div class="dashboard-page">
    <header class="top">
      <div>
        <p class="eyebrow">A 股行情概览</p>
        <h1>市场看板</h1>
      </div>
      <div class="stats">
        <p><span>{{ quotes.length }}</span> 自选股</p>
        <p>
          平均涨跌
          <span :class="marketAvg >= 0 ? 'up' : 'down'">{{ marketAvg >= 0 ? '+' : '' }}{{ marketAvg.toFixed(2) }}%</span>
        </p>
      </div>
    </header>

    <div v-if="loading" class="loading">加载行情中…</div>
    <div v-else-if="errorText" class="error">{{ errorText }}</div>

    <section v-else class="board">
      <div class="toolbar">
        <div class="tabs">
          <RouterLink to="/market" class="tab tab--link">查看全部行情 →</RouterLink>
        </div>
        <form class="search" @submit.prevent="doSearch">
          <input
            v-model="keyword"
            type="search"
            placeholder="搜索代码或名称，如 平安、600000"
          />
          <button type="submit" class="search-btn" :disabled="searching">
            {{ searching ? '…' : '搜索' }}
          </button>
        </form>
      </div>

      <div v-if="searchItems.length" class="search-results">
        <p class="sub-title">搜索结果（点击进入个股日线）</p>
        <table class="table">
          <thead>
            <tr>
              <th>代码</th>
              <th>名称</th>
              <th>vtSymbol</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="it in searchItems" :key="it.ts_code">
              <td class="mono">{{ it.ts_code }}</td>
              <td>{{ it.name }}</td>
              <td class="mono muted">{{ it.vt_symbol }}</td>
              <td>
                <RouterLink :to="{ path: '/market/stock', query: { ts_code: it.ts_code } }" class="link">
                  日线 →
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="searchErr" class="error">{{ searchErr }}</p>

      <div class="cols">
        <div class="col">
          <p class="sub-title">涨幅榜</p>
          <table class="table">
            <thead>
              <tr><th>名称</th><th>现价</th><th>涨跌幅</th></tr>
            </thead>
            <tbody>
              <tr v-for="q in topGainers" :key="q.code">
                <td>{{ q.name }}</td>
                <td class="mono">{{ q.last.toFixed(2) }}</td>
                <td class="up mono">+{{ q.pct.toFixed(2) }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="col">
          <p class="sub-title">跌幅榜</p>
          <table class="table">
            <thead>
              <tr><th>名称</th><th>现价</th><th>涨跌幅</th></tr>
            </thead>
            <tbody>
              <tr v-for="q in topLosers" :key="q.code">
                <td>{{ q.name }}</td>
                <td class="mono">{{ q.last.toFixed(2) }}</td>
                <td class="down mono">{{ q.pct.toFixed(2) }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <p class="sub-title">自选股近 90 日走势（收盘价）</p>
      <table class="table">
        <thead>
          <tr><th>名称</th><th>现价</th><th>涨跌</th><th>涨跌幅</th></tr>
        </thead>
        <tbody>
          <tr v-for="q in quotes" :key="q.code">
            <td>
              <RouterLink :to="{ path: '/market/stock', query: { ts_code: q.code } }" class="link">
                {{ q.name }}
              </RouterLink>
            </td>
            <td class="mono">{{ q.last.toFixed(2) }}</td>
            <td class="mono" :class="q.change >= 0 ? 'up' : 'down'">
              {{ q.change >= 0 ? '+' : '' }}{{ q.change.toFixed(2) }}
            </td>
            <td class="mono" :class="q.pct >= 0 ? 'up' : 'down'">
              {{ q.pct >= 0 ? '+' : '' }}{{ q.pct.toFixed(2) }}%
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  max-width: 1200px;
  margin: 0 auto;
  padding: 6.8rem 1rem 2rem;
}
.top {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: end;
  margin-bottom: 0.8rem;
}
.eyebrow {
  margin: 0;
  color: var(--bq-accent-soft);
  font-size: 0.78rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.top h1 {
  margin: 0.4rem 0 0;
  font-size: 1.4rem;
  color: var(--bq-text);
}
.stats {
  display: flex;
  gap: 0.6rem;
}
.stats p {
  margin: 0;
  padding: 0.42rem 0.65rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--bq-muted);
  font-size: 0.82rem;
}
.stats span {
  color: var(--bq-text);
  font-weight: 600;
}
.board {
  border-radius: 16px;
  padding: 0.9rem;
  background: linear-gradient(180deg, rgba(18, 27, 49, 0.9), rgba(11, 18, 33, 0.86));
  box-shadow: 0 0 0 1px var(--bq-edge) inset, 0 18px 38px rgba(0, 0, 0, 0.36);
}
.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: center;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}
.tabs {
  display: flex;
  gap: 0.4rem;
}
.tab {
  border: 0;
  border-radius: 999px;
  padding: 0.42rem 0.9rem;
  font-size: 0.82rem;
  color: #0f0d0a;
  background: linear-gradient(140deg, var(--bq-accent) 0%, #8d6238 100%);
  text-decoration: none;
  font-weight: 600;
}
.search {
  display: flex;
  gap: 0.4rem;
  flex: 1;
  min-width: 280px;
  max-width: 420px;
}
.search input {
  flex: 1;
  border: 1px solid rgba(169, 190, 221, 0.2);
  border-radius: 10px;
  background: rgba(8, 12, 21, 0.72);
  color: var(--bq-text);
  padding: 0.48rem 0.62rem;
}
.search-btn {
  border: 0;
  border-radius: 10px;
  padding: 0.48rem 0.85rem;
  background: rgba(255, 255, 255, 0.1);
  color: var(--bq-text);
  cursor: pointer;
  font-weight: 600;
}
.sub-title {
  margin: 0.9rem 0 0.4rem;
  font-size: 0.82rem;
  color: var(--bq-muted);
}
.cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.9rem;
}
.table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  text-align: left;
  font-size: 0.84rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0.5rem 0.4rem;
  color: var(--bq-muted);
}
th {
  color: var(--bq-text);
  white-space: nowrap;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
.muted {
  color: rgba(168, 184, 207, 0.7);
}
.up {
  color: #ef7d7d;
}
.down {
  color: #57d991;
}
.link {
  color: #9fc3ff;
  text-decoration: none;
}
.link:hover {
  text-decoration: underline;
}
.search-results {
  margin-bottom: 0.4rem;
}
.loading,
.error {
  padding: 2rem;
  text-align: center;
  color: var(--bq-muted);
}
.error {
  color: #f59e9b;
}
@media (max-width: 860px) {
  .cols {
    grid-template-columns: 1fr;
  }
  .top {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>