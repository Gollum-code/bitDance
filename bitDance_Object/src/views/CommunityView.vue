<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { fetchPosts, fetchTrending, type PostSummaryDTO } from '../services/community'

const router = useRouter()

const q = ref('')
const page = ref(1)
const size = ref(10)
const total = ref(0)
const items = ref<PostSummaryDTO[]>([])
const trending = ref<PostSummaryDTO[]>([])
const loading = ref(false)
const err = ref('')

const totalPages = () => Math.max(1, Math.ceil(total.value / size.value))

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

async function loadList() {
  loading.value = true
  err.value = ''
  try {
    const data = await fetchPosts({ q: q.value, page: page.value, size: size.value })
    items.value = data.items
    total.value = data.total
  } catch (e) {
    err.value = e instanceof Error ? e.message : '加载失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

async function loadTrending() {
  try {
    trending.value = await fetchTrending(8)
  } catch {
    trending.value = []
  }
}

function goNew() {
  void router.push('/community/new')
}

let searchTimer: ReturnType<typeof setTimeout> | undefined
function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    void loadList()
  }, 320)
}

function prevPage() {
  if (page.value > 1) {
    page.value -= 1
    void loadList()
  }
}

function nextPage() {
  if (page.value < totalPages()) {
    page.value += 1
    void loadList()
  }
}

onMounted(() => {
  void loadList()
  void loadTrending()
})
</script>

<template>
  <div class="community-page">
    <header class="head">
      <div>
        <h1>bitDance 社区</h1>
        <p>论坛式讨论区，分享实战经验、答疑与策略思路</p>
      </div>
      <button type="button" @click="goNew">发布帖子</button>
    </header>

    <main class="layout">
      <section class="feed">
        <div class="tools">
          <input
            v-model="q"
            type="search"
            placeholder="搜索标题或正文…"
            @input="onSearchInput"
          />
        </div>

        <p v-if="loading" class="hint">加载中…</p>
        <p v-else-if="err" class="hint err">{{ err }}</p>

        <RouterLink
          v-for="post in items"
          :key="post.id"
          :to="`/community/post/${post.id}`"
          class="post"
        >
          <div class="post-main">
            <h2>{{ post.title }}</h2>
            <p>{{ post.authorUsername }} · {{ formatTime(post.createdAt) }}</p>
            <p class="excerpt">{{ post.excerpt }}</p>
          </div>
          <div class="post-meta">
            <p>♥ {{ post.likeCount }}</p>
            <p>{{ post.commentCount }} 评论</p>
          </div>
        </RouterLink>

        <div v-if="!loading && !items.length && !err" class="hint">暂无帖子，快来发第一条吧。</div>

        <div v-if="total > size" class="pager">
          <button type="button" :disabled="page <= 1" @click="prevPage">上一页</button>
          <span class="pager-info">{{ page }} / {{ totalPages() }}</span>
          <button type="button" :disabled="page >= totalPages()" @click="nextPage">下一页</button>
        </div>
      </section>

      <aside class="side">
        <section class="card">
          <h3>热门话题</h3>
          <p class="side-hint">按点赞量排序的高热度帖子</p>
          <ol class="hot-list">
            <li v-for="h in trending" :key="h.id">
              <RouterLink :to="`/community/post/${h.id}`" class="hot-link">
                <span class="hot-title">{{ h.title }}</span>
                <span class="hot-meta">♥ {{ h.likeCount }}</span>
              </RouterLink>
            </li>
          </ol>
          <p v-if="!trending.length" class="hint small">暂无数据</p>
        </section>
        <section class="card">
          <h3>社区说明</h3>
          <ul>
            <li>仅讨论量化与交易系统相关内容</li>
            <li>分享策略时建议附回测区间与参数</li>
            <li>文明发言；广告与灌水将被处理</li>
          </ul>
        </section>
      </aside>
    </main>
  </div>
</template>

<style scoped>
.community-page {
  min-height: 100vh;
  max-width: 1240px;
  margin: 0 auto;
  padding: 6.8rem 1rem 2rem;
}

.head {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: center;
  margin-bottom: 0.8rem;
}

.head h1 {
  margin: 0;
  color: var(--bq-text);
  font-size: 1.45rem;
}

.head p {
  margin: 0.35rem 0 0;
  color: var(--bq-muted);
}

.head button {
  border: 0;
  border-radius: 10px;
  padding: 0.55rem 0.88rem;
  font-weight: 600;
  color: #0d0b07;
  cursor: pointer;
  background: linear-gradient(140deg, var(--bq-accent) 0%, #8f673c 100%);
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 290px;
  gap: 0.9rem;
}

.feed,
.card {
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(18, 27, 49, 0.9), rgba(11, 18, 33, 0.86));
  box-shadow:
    0 0 0 1px var(--bq-edge) inset,
    0 18px 38px rgba(0, 0, 0, 0.36);
}

.feed {
  padding: 0.9rem;
}

.tools {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  margin-bottom: 0.8rem;
}

.tools input {
  border: 0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--bq-text);
  padding: 0.48rem 0.62rem;
}

.post {
  display: grid;
  gap: 0.7rem;
  grid-template-columns: minmax(0, 1fr) 95px;
  padding: 0.75rem 0.2rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  text-decoration: none;
  color: inherit;
  cursor: pointer;
}

.post:first-of-type {
  border-top: 0;
}

.post h2 {
  margin: 0;
  font-size: 1rem;
  color: #eee8de;
}

.post-main p {
  margin: 0.4rem 0 0;
  color: var(--bq-muted);
  font-size: 0.82rem;
}

.excerpt {
  margin-top: 0.35rem !important;
  font-size: 0.78rem !important;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.post-meta {
  text-align: right;
  color: var(--bq-muted);
  font-size: 0.78rem;
}

.card {
  padding: 0.85rem;
}

.card + .card {
  margin-top: 0.8rem;
}

.card h3 {
  margin: 0;
  font-size: 0.95rem;
  color: var(--bq-text);
}

.side-hint {
  margin: 0.35rem 0 0.5rem;
  font-size: 0.75rem;
  color: var(--bq-muted);
}

.hot-list {
  margin: 0;
  padding-left: 1.05rem;
}

.hot-link {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  align-items: baseline;
  text-decoration: none;
  color: var(--bq-muted);
  font-size: 0.84rem;
  line-height: 1.45;
}

.hot-link:hover .hot-title {
  color: var(--bq-accent-soft);
}

.hot-title {
  flex: 1;
  min-width: 0;
}

.hot-meta {
  flex-shrink: 0;
  font-size: 0.75rem;
  color: var(--bq-muted);
}

.card ul {
  margin: 0.65rem 0 0;
  padding-left: 1.05rem;
  color: var(--bq-muted);
  line-height: 1.62;
  font-size: 0.84rem;
}

.hint {
  color: var(--bq-muted);
  font-size: 0.88rem;
}

.hint.small {
  margin: 0.5rem 0 0;
  font-size: 0.8rem;
}

.hint.err {
  color: #f59e9b;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.65rem;
  margin-top: 0.85rem;
}

.pager button {
  border: 1px solid var(--bq-edge);
  border-radius: 8px;
  padding: 0.35rem 0.65rem;
  background: rgba(255, 255, 255, 0.04);
  color: var(--bq-text);
  cursor: pointer;
  font-size: 0.82rem;
}

.pager button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pager-info {
  font-size: 0.82rem;
  color: var(--bq-muted);
}

@media (max-width: 900px) {
  .community-page {
    padding-top: 5.9rem;
  }

  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
