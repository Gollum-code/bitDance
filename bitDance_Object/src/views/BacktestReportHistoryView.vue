<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { marked } from 'marked'
import { FileDown, Trash2 } from 'lucide-vue-next'
import { useAuth } from '../state/auth'
import {
  listBacktestReports,
  removeBacktestReport,
  type BacktestReportHistoryEntry,
} from '../state/backtestReportHistory'

const auth = useAuth()

marked.setOptions({ gfm: true, breaks: true })

const items = ref<BacktestReportHistoryEntry[]>([])
const expandedId = ref<string | null>(null)
const exportingId = ref<string | null>(null)
const exportError = ref<string | null>(null)

const userId = computed(() => auth.user.value?.id)

function load() {
  const uid = userId.value
  if (uid == null) {
    items.value = []
    return
  }
  items.value = listBacktestReports(uid)
}

function formatTime(ts: number) {
  try {
    return new Date(ts).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return String(ts)
  }
}

function htmlBody(md: string) {
  try {
    const out = marked.parse(md, { async: false })
    return typeof out === 'string' ? out : String(out)
  } catch {
    return `<p>${md.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p>`
  }
}

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

function handleRemove(id: string) {
  const uid = userId.value
  if (uid == null) return
  removeBacktestReport(uid, id)
  if (expandedId.value === id) expandedId.value = null
  load()
}

async function handleExport(item: BacktestReportHistoryEntry) {
  if (exportingId.value != null) return
  exportingId.value = item.id
  exportError.value = null
  try {
    const { exportBacktestReportToPdf } = await import('../utils/exportBacktestReportPdf')
    await exportBacktestReportToPdf(item.body, item.createdAt)
  } catch {
    exportError.value = '导出 PDF 失败，请稍后重试。'
  } finally {
    exportingId.value = null
  }
}

onMounted(() => {
  void auth.init().then(() => load())
})
</script>

<template>
  <div class="history-page">
    <header class="head">
      <div>
        <p class="eyebrow">Reports</p>
        <h1>回测报告历史记录</h1>
        <p class="lead">
          在「我的策略」中通过 bitDance 智能体生成回测报告后，正文将自动保存在本机浏览器（按账号区分）。
        </p>
      </div>
      <div class="head-actions">
        <RouterLink to="/strategies" class="btn-primary">前往我的策略</RouterLink>
        <RouterLink to="/member" class="btn-ghost">会员中心</RouterLink>
      </div>
    </header>

    <p v-if="exportError" class="export-error" role="alert">{{ exportError }}</p>

    <section v-if="items.length === 0" class="empty">
      <p>暂无记录。请先在「我的策略」运行回测，再在右下角 AI 面板中点击「生成回测报告」。</p>
      <RouterLink to="/strategies" class="btn-primary">去我的策略</RouterLink>
    </section>

    <ul v-else class="list">
      <li v-for="item in items" :key="item.id" class="card">
        <div class="card-top">
          <time class="time" :datetime="new Date(item.createdAt).toISOString()">{{
            formatTime(item.createdAt)
          }}</time>
          <div class="card-actions">
            <button
              type="button"
              class="icon-btn"
              :aria-label="exportingId === item.id ? '正在导出 PDF' : '导出为 PDF'"
              :disabled="exportingId != null"
              @click="handleExport(item)"
            >
              <FileDown class="ic" aria-hidden="true" />
            </button>
            <button type="button" class="icon-btn" aria-label="删除此条记录" @click="handleRemove(item.id)">
              <Trash2 class="ic" aria-hidden="true" />
            </button>
          </div>
        </div>
        <div
          class="report-md"
          :class="{ 'report-md--collapsed': expandedId !== item.id }"
          v-html="htmlBody(item.body)"
        />
        <button type="button" class="toggle" @click="toggleExpand(item.id)">
          {{ expandedId === item.id ? '收起全文' : '查看全文' }}
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.history-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 5.5rem 1.25rem 3rem;
}

.head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 2rem;
}

.eyebrow {
  margin: 0;
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--bq-accent-soft);
}

h1 {
  margin: 0.35rem 0 0.5rem;
  font-size: 1.65rem;
  font-weight: 650;
  color: var(--bq-text);
}

.lead {
  margin: 0;
  max-width: 36rem;
  font-size: 0.9rem;
  line-height: 1.65;
  color: rgba(231, 229, 228, 0.72);
}

.head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.btn-primary,
.btn-ghost {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 0.95rem;
  border-radius: 999px;
  font-size: 0.84rem;
  font-weight: 600;
  text-decoration: none;
  transition:
    background 0.2s ease,
    color 0.2s ease;
}

.btn-primary {
  background: linear-gradient(180deg, #b3874f 0%, #7f5731 100%);
  color: #0c0c0c;
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.35);
}

.btn-ghost {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(245, 245, 244, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.empty {
  padding: 2rem 1.25rem;
  border-radius: 1rem;
  text-align: center;
  background: rgba(255, 255, 255, 0.04);
  box-shadow: 0 0 0 1px rgba(166, 127, 74, 0.15);
}

.empty p {
  margin: 0 0 1.25rem;
  font-size: 0.9rem;
  line-height: 1.6;
  color: rgba(231, 229, 228, 0.78);
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.card {
  padding: 1rem 1.1rem;
  border-radius: 1rem;
  background: rgba(16, 25, 41, 0.55);
  box-shadow:
    0 0 0 1px rgba(166, 127, 74, 0.14),
    0 12px 32px rgba(0, 0, 0, 0.35);
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.65rem;
}

.time {
  font-size: 0.78rem;
  color: rgba(198, 153, 96, 0.85);
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.export-error {
  margin: 0 0 1rem;
  padding: 0.55rem 0.85rem;
  border-radius: 0.5rem;
  font-size: 0.84rem;
  color: #fecaca;
  background: rgba(240, 88, 88, 0.15);
  box-shadow: 0 0 0 1px rgba(240, 88, 88, 0.25);
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(245, 245, 244, 0.75);
  cursor: pointer;
  transition: background 0.15s ease;
}

.icon-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
  color: rgba(245, 245, 244, 0.95);
}

.icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.card-actions .icon-btn:last-child:hover:not(:disabled) {
  background: rgba(240, 88, 88, 0.18);
  color: #fecaca;
}

.ic {
  width: 1rem;
  height: 1rem;
}

.report-md {
  font-size: 0.8125rem;
  line-height: 1.55;
  position: relative;
  word-break: break-word;
}

.report-md--collapsed {
  max-height: 13rem;
  overflow: hidden;
}

.report-md--collapsed::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 3.25rem;
  background: linear-gradient(to bottom, transparent, rgba(16, 25, 41, 0.96));
  pointer-events: none;
}

.toggle {
  margin-top: 0.65rem;
  padding: 0;
  border: none;
  background: none;
  font-size: 0.8rem;
  font-weight: 600;
  color: rgba(147, 197, 253, 0.92);
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.report-md :deep(h1),
.report-md :deep(h2),
.report-md :deep(h3) {
  color: rgba(245, 245, 244, 0.96);
  margin: 0.65rem 0 0.4rem;
  font-weight: 650;
}

.report-md :deep(h1:first-child),
.report-md :deep(h2:first-child),
.report-md :deep(h3:first-child) {
  margin-top: 0;
}

.report-md :deep(p) {
  margin: 0.4rem 0;
  color: rgba(245, 245, 244, 0.9);
}

.report-md :deep(ul),
.report-md :deep(ol) {
  margin: 0.4rem 0;
  padding-left: 1.15rem;
}

.report-md :deep(li) {
  margin: 0.2rem 0;
}

.report-md :deep(blockquote) {
  margin: 0.45rem 0;
  padding: 0.35rem 0.55rem;
  border-left: 3px solid rgba(191, 147, 83, 0.45);
  background: rgba(0, 0, 0, 0.2);
  color: rgba(220, 215, 208, 0.92);
}

.report-md :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.82em;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  padding: 0.1rem 0.35rem;
}

.report-md :deep(pre) {
  margin: 0.5rem 0;
  padding: 0.55rem 0.65rem;
  border-radius: 0.45rem;
  background: rgba(0, 0, 0, 0.45);
  overflow-x: auto;
}

.report-md :deep(pre code) {
  background: transparent;
  padding: 0;
  font-size: 0.78rem;
}

.report-md :deep(strong) {
  color: rgba(253, 246, 236, 0.98);
  font-weight: 650;
}

.report-md :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.5rem 0;
  font-size: 0.78rem;
}

.report-md :deep(th),
.report-md :deep(td) {
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0.35rem 0.45rem;
}

.report-md :deep(th) {
  background: rgba(191, 147, 83, 0.12);
}

.report-md :deep(a) {
  color: rgba(147, 197, 253, 0.95);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.report-md :deep(hr) {
  margin: 0.65rem 0;
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}
</style>
