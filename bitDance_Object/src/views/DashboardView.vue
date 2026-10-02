<script setup lang="ts">
import { computed, ref } from 'vue'

type MetricRow = {
  name: string
  desc: string
  tags: string[]
  markets: Record<string, boolean>
}

const marketTabs = ['全市场', '现货分析', '衍生品交易', '链上观测'] as const
const activeTab = ref<(typeof marketTabs)[number]>('全市场')
const keyword = ref('')

const marketColumns = ['BTC', 'ETH', 'SOL', 'BNB', 'TON', 'XRP', 'DOGE', 'SAND']

const rows: MetricRow[] = [
  {
    name: 'drawdown_from_high',
    desc: '从历史高位 ATH 的回撤百分比',
    tags: ['现货分析'],
    markets: { BTC: true, ETH: true, SOL: true, BNB: true, TON: true, XRP: true, DOGE: true, SAND: false },
  },
  {
    name: 'market_cap',
    desc: '流通市值',
    tags: ['现货分析'],
    markets: { BTC: true, ETH: true, SOL: true, BNB: true, TON: true, XRP: true, DOGE: true, SAND: true },
  },
  {
    name: 'futures_open_interest',
    desc: '合约未平仓量',
    tags: ['衍生品交易'],
    markets: { BTC: true, ETH: true, SOL: true, BNB: true, TON: false, XRP: true, DOGE: true, SAND: true },
  },
  {
    name: 'perp_funding',
    desc: '永续资金费率',
    tags: ['衍生品交易'],
    markets: { BTC: true, ETH: true, SOL: true, BNB: true, TON: false, XRP: true, DOGE: true, SAND: true },
  },
  {
    name: 'active_address_24h',
    desc: '近 24 小时活跃地址数',
    tags: ['链上观测'],
    markets: { BTC: true, ETH: true, SOL: true, BNB: true, TON: true, XRP: false, DOGE: false, SAND: true },
  },
  {
    name: 'new_address_24h',
    desc: '近 24 小时新增地址数',
    tags: ['链上观测'],
    markets: { BTC: true, ETH: true, SOL: true, BNB: true, TON: true, XRP: false, DOGE: false, SAND: false },
  },
]

const filteredRows = computed(() =>
  rows.filter((row) => {
    const hitTab = activeTab.value === '全市场' || row.tags.includes(activeTab.value)
    const hitKey =
      keyword.value.trim().length === 0 ||
      row.name.toLowerCase().includes(keyword.value.trim().toLowerCase()) ||
      row.desc.includes(keyword.value.trim())
    return hitTab && hitKey
  }),
)
</script>

<template>
  <div class="dashboard-page">
    <header class="top">
      <div>
        <p class="eyebrow">统一数据覆盖看板</p>
        <h1>市场-数据覆盖矩阵</h1>
      </div>
      <div class="stats">
        <p><span>{{ rows.length }}</span> 指标项</p>
        <p><span>{{ marketColumns.length }}</span> 币种</p>
      </div>
    </header>

    <section class="board">
      <div class="toolbar">
        <div class="tabs">
          <button
            v-for="tab in marketTabs"
            :key="tab"
            type="button"
            class="tab"
            :class="{ 'tab--on': activeTab === tab }"
            @click="activeTab = tab"
          >
            {{ tab }}
          </button>
        </div>
        <input v-model="keyword" type="text" placeholder="搜索指标名称或描述..." />
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>数据名称</th>
              <th>数据说明</th>
              <th v-for="mk in marketColumns" :key="mk">{{ mk }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRows" :key="row.name">
              <td class="name">{{ row.name }}</td>
              <td class="desc">{{ row.desc }}</td>
              <td v-for="mk in marketColumns" :key="`${row.name}-${mk}`" class="status">
                <span :class="row.markets[mk] ? 'ok' : 'no'">{{ row.markets[mk] ? '✓' : '·' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  max-width: 1280px;
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
  box-shadow:
    0 0 0 1px var(--bq-edge) inset,
    0 18px 38px rgba(0, 0, 0, 0.36);
}

.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  margin-bottom: 0.75rem;
}

.tabs {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.tab {
  border: 0;
  border-radius: 999px;
  padding: 0.35rem 0.66rem;
  font-size: 0.8rem;
  color: var(--bq-muted);
  background: rgba(255, 255, 255, 0.04);
}

.tab--on {
  color: #0f0d0a;
  background: linear-gradient(140deg, var(--bq-accent) 0%, #8d6238 100%);
}

input {
  min-width: 250px;
  border: 0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--bq-text);
  padding: 0.48rem 0.62rem;
}

input::placeholder {
  color: rgba(168, 184, 207, 0.7);
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  text-align: left;
  font-size: 0.82rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0.54rem 0.5rem;
  color: var(--bq-muted);
}

th {
  color: var(--bq-text);
  white-space: nowrap;
}

.name {
  color: #ede8de;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.desc {
  min-width: 210px;
}

.status {
  text-align: center;
}

.ok {
  color: #57d991;
}

.no {
  color: rgba(150, 150, 150, 0.75);
}

@media (max-width: 860px) {
  .dashboard-page {
    padding-top: 5.9rem;
  }

  .top {
    flex-direction: column;
    align-items: flex-start;
  }

  .toolbar {
    flex-direction: column;
  }

  input {
    min-width: 0;
    width: 100%;
  }
}
</style>
