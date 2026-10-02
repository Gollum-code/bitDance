<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { Search } from 'lucide-vue-next'
import { listMarketStocks, type StockBasicItem } from '../services/market'

const router = useRouter()
const q = ref('')
const loading = ref(false)
const errorMessage = ref('')
const items = ref<StockBasicItem[]>([])

let debounceTimer: ReturnType<typeof setTimeout> | null = null

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await listMarketStocks(q.value || undefined, 100)
    items.value = res.items ?? []
  } catch (e) {
    errorMessage.value = e instanceof Error ? e.message : '加载失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

function goStock(row: StockBasicItem) {
  router.push({ path: '/market/stock', query: { ts_code: row.ts_code } })
}

onMounted(() => {
  void load()
})

watch(q, () => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    void load()
  }, 320)
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1>A 股行情</h1>
        <p class="sub">数据来自 TuShare（日线）；点进个股可看 K 线并同步到本地库后回测。</p>
      </div>
      <RouterLink to="/" class="ghost">← 返回首页</RouterLink>
    </header>

    <section class="card">
      <div class="toolbar">
        <label class="search">
          <Search class="ic" aria-hidden="true" />
          <input v-model.trim="q" type="search" placeholder="代码或名称，如 平安、600000" />
        </label>
        <span v-if="loading" class="muted">加载中…</span>
      </div>
      <p v-if="errorMessage" class="err">{{ errorMessage }}</p>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>代码</th>
              <th>名称</th>
              <th>行业</th>
              <th>上市日</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in items" :key="row.ts_code">
              <td class="mono">{{ row.ts_code }}</td>
              <td>{{ row.name }}</td>
              <td class="muted">{{ row.industry || '—' }}</td>
              <td class="muted">{{ row.list_date || '—' }}</td>
              <td class="actions">
                <button type="button" class="linkish" @click="goStock(row)">查看 K 线</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="!loading && items.length === 0" class="empty">无结果，请尝试其他关键字。</p>
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
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}
.head h1 {
  margin: 0;
  font-size: 1.35rem;
  color: var(--bq-text);
}
.sub {
  margin: 0.35rem 0 0;
  font-size: 0.85rem;
  color: var(--bq-muted);
  max-width: 52ch;
  line-height: 1.45;
}
.ghost {
  font-size: 0.82rem;
  color: #9eb6d8;
  text-decoration: none;
  border: 1px solid rgba(169, 190, 221, 0.25);
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
}
.ghost:hover {
  border-color: rgba(169, 190, 221, 0.45);
}
.card {
  border-radius: 16px;
  padding: 1rem;
  background: linear-gradient(160deg, rgba(18, 27, 49, 0.92), rgba(11, 18, 33, 0.9));
  box-shadow: 0 0 0 1px rgba(138, 158, 191, 0.22) inset, 0 20px 50px rgba(0, 0, 0, 0.45);
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.search {
  flex: 1;
  min-width: 220px;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  border: 1px solid rgba(169, 190, 221, 0.2);
  border-radius: 12px;
  padding: 0.45rem 0.6rem;
  background: rgba(8, 12, 21, 0.72);
}
.search input {
  flex: 1;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--bq-text);
  font-size: 0.88rem;
}
.ic {
  width: 1rem;
  height: 1rem;
  color: #8fa4c4;
}
.muted {
  color: var(--bq-muted);
  font-size: 0.78rem;
}
.err {
  margin: 0.6rem 0 0;
  color: #ff8686;
  font-size: 0.82rem;
}
.table-wrap {
  margin-top: 0.75rem;
  overflow: auto;
  border-radius: 12px;
  border: 1px solid rgba(128, 152, 190, 0.18);
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}
th,
td {
  padding: 0.55rem 0.65rem;
  text-align: left;
  border-bottom: 1px solid rgba(103, 126, 162, 0.15);
}
th {
  color: #9eb1cb;
  font-weight: 600;
  background: rgba(10, 17, 30, 0.55);
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  color: #dbe8ff;
}
.actions {
  text-align: right;
}
.linkish {
  border: 0;
  background: transparent;
  color: #7ec8ff;
  cursor: pointer;
  font-size: 0.82rem;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.empty {
  padding: 1rem;
  color: var(--bq-muted);
  font-size: 0.82rem;
}
</style>
