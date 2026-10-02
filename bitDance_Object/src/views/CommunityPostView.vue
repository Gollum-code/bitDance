<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MarkdownBody from '../components/bitdance/MarkdownBody.vue'
import {
  createComment,
  fetchComments,
  fetchPost,
  toggleCommentLike,
  togglePostLike,
  type CommentDTO,
  type PostDetailDTO,
} from '../services/community'
import { getToken } from '../services/auth'

const route = useRoute()
const router = useRouter()

const postId = computed(() => Number(route.params.id))
const post = ref<PostDetailDTO | null>(null)
const comments = ref<CommentDTO[]>([])
const sort = ref<'new' | 'likes'>('new')
const loading = ref(true)
const loadErr = ref('')
const commentBody = ref('')
const commentSubmitting = ref(false)
const commentErr = ref('')

const authed = computed(() => Boolean(getToken()))

function formatTime(iso: string) {
  try {
    const d = new Date(iso)
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

async function loadPost() {
  loadErr.value = ''
  loading.value = true
  try {
    post.value = await fetchPost(postId.value)
  } catch (e) {
    loadErr.value = e instanceof Error ? e.message : '加载失败'
    post.value = null
  } finally {
    loading.value = false
  }
}

async function loadComments() {
  try {
    comments.value = await fetchComments(postId.value, sort.value)
  } catch {
    comments.value = []
  }
}

async function onTogglePostLike() {
  if (!authed.value) {
    await router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }
  if (!post.value) return
  try {
    const r = await togglePostLike(post.value.id)
    post.value = {
      ...post.value,
      likedByMe: r.liked,
      likeCount: r.likeCount,
    }
  } catch {
    /* toast optional */
  }
}

async function onToggleCommentLike(c: CommentDTO) {
  if (!authed.value) {
    await router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }
  try {
    const r = await toggleCommentLike(c.id)
    const idx = comments.value.findIndex((x) => x.id === c.id)
    if (idx >= 0) {
      const row = comments.value[idx]
      if (row) {
        comments.value[idx] = {
          ...row,
          likedByMe: r.liked,
          likeCount: r.likeCount,
        }
      }
    }
  } catch {
    /* ignore */
  }
}

async function submitComment() {
  commentErr.value = ''
  const body = commentBody.value.trim()
  if (!body) {
    commentErr.value = '请输入评论内容'
    return
  }
  if (!authed.value) {
    await router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }
  commentSubmitting.value = true
  try {
    await createComment(postId.value, body)
    commentBody.value = ''
    await loadComments()
    await loadPost()
  } catch (e) {
    commentErr.value = e instanceof Error ? e.message : '发表失败'
  } finally {
    commentSubmitting.value = false
  }
}

onMounted(async () => {
  await loadPost()
  await loadComments()
})

watch(postId, async () => {
  await loadPost()
  await loadComments()
})

watch(sort, async () => {
  await loadComments()
})
</script>

<template>
  <div class="post-page">
    <button type="button" class="back" @click="router.push('/community')">← 返回列表</button>

    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="loadErr" class="err">{{ loadErr }}</p>

    <article v-else-if="post" class="article card">
      <header class="article-head">
        <h1>{{ post.title }}</h1>
        <p class="meta">
          {{ post.authorUsername }} · {{ formatTime(post.createdAt) }}
        </p>
      </header>
      <MarkdownBody class="body" :source="post.content" />
      <footer class="article-foot">
        <button
          type="button"
          class="like"
          :class="{ on: post.likedByMe }"
          @click="onTogglePostLike"
        >
          ♥ {{ post.likeCount }}
        </button>
        <span class="muted">{{ post.commentCount }} 条评论</span>
      </footer>
    </article>

    <section v-if="post" class="comments card">
      <div class="comments-head">
        <h2>评论</h2>
        <div class="sort">
          <button type="button" :class="{ active: sort === 'new' }" @click="sort = 'new'">
            按时间
          </button>
          <button type="button" :class="{ active: sort === 'likes' }" @click="sort = 'likes'">
            按点赞
          </button>
        </div>
      </div>

      <div class="composer">
        <textarea v-model="commentBody" rows="3" placeholder="写下你的看法…" />
        <div class="composer-row">
          <p v-if="commentErr" class="err small">{{ commentErr }}</p>
          <button
            type="button"
            class="primary"
            :disabled="commentSubmitting"
            @click="submitComment"
          >
            {{ commentSubmitting ? '发送中…' : '发表评论' }}
          </button>
        </div>
      </div>

      <ul class="comment-list">
        <li v-for="c in comments" :key="c.id" class="comment-item">
          <div class="comment-top">
            <span class="who">{{ c.authorUsername }}</span>
            <span class="when">{{ formatTime(c.createdAt) }}</span>
          </div>
          <p class="comment-body">{{ c.body }}</p>
          <button
            type="button"
            class="like small"
            :class="{ on: c.likedByMe }"
            @click="onToggleCommentLike(c)"
          >
            ♥ {{ c.likeCount }}
          </button>
        </li>
      </ul>
      <p v-if="!comments.length" class="muted empty">暂无评论，抢沙发</p>
    </section>
  </div>
</template>

<style scoped>
.post-page {
  max-width: 820px;
  margin: 0 auto;
  padding: 6.8rem 1rem 2.5rem;
}

.back {
  margin-bottom: 0.75rem;
  border: 0;
  background: transparent;
  color: var(--bq-accent-soft);
  cursor: pointer;
  font-size: 0.9rem;
}

.muted {
  color: var(--bq-muted);
}

.err {
  color: #f59e9b;
}

.err.small {
  margin: 0;
  font-size: 0.82rem;
}

.card {
  border-radius: 16px;
  padding: 1rem 1.1rem;
  margin-bottom: 0.9rem;
  background: linear-gradient(180deg, rgba(18, 27, 49, 0.9), rgba(11, 18, 33, 0.86));
  box-shadow:
    0 0 0 1px var(--bq-edge) inset,
    0 18px 38px rgba(0, 0, 0, 0.36);
}

.article-head h1 {
  margin: 0;
  font-size: 1.35rem;
  color: #eee8de;
}

.meta {
  margin: 0.45rem 0 0;
  color: var(--bq-muted);
  font-size: 0.85rem;
}

.body {
  margin: 1rem 0 0;
}

.article-foot {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.like {
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 999px;
  padding: 0.28rem 0.65rem;
  background: rgba(255, 255, 255, 0.04);
  color: var(--bq-muted);
  cursor: pointer;
  font-size: 0.84rem;
}

.like.on {
  border-color: rgba(191, 147, 83, 0.45);
  color: var(--bq-accent-soft);
}

.like.small {
  margin-top: 0.35rem;
}

.comments-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.comments-head h2 {
  margin: 0;
  font-size: 1.05rem;
  color: var(--bq-text);
}

.sort {
  display: flex;
  gap: 0.35rem;
}

.sort button {
  border: 1px solid transparent;
  border-radius: 999px;
  padding: 0.22rem 0.55rem;
  font-size: 0.78rem;
  background: rgba(255, 255, 255, 0.04);
  color: var(--bq-muted);
  cursor: pointer;
}

.sort button.active {
  border-color: rgba(191, 147, 83, 0.35);
  color: var(--bq-accent-soft);
}

.composer textarea {
  width: 100%;
  box-sizing: border-box;
  border: 0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--bq-text);
  padding: 0.55rem 0.65rem;
  font-size: 0.92rem;
  resize: vertical;
}

.composer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.45rem;
}

.primary {
  border: 0;
  border-radius: 10px;
  padding: 0.45rem 0.85rem;
  font-weight: 600;
  font-size: 0.85rem;
  color: #0d0b07;
  cursor: pointer;
  background: linear-gradient(140deg, var(--bq-accent) 0%, #8f673c 100%);
}

.primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.comment-list {
  list-style: none;
  margin: 0.85rem 0 0;
  padding: 0;
}

.comment-item {
  padding: 0.65rem 0;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.comment-item:first-child {
  border-top: 0;
}

.comment-top {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.8rem;
}

.who {
  color: #ddd;
}

.when {
  color: var(--bq-muted);
}

.comment-body {
  margin: 0.35rem 0 0;
  font-size: 0.9rem;
  line-height: 1.55;
  color: var(--bq-text);
}

.empty {
  margin: 0.5rem 0 0;
  font-size: 0.88rem;
}

@media (max-width: 900px) {
  .post-page {
    padding-top: 5.9rem;
  }
}
</style>
