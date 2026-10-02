<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import MarkdownBody from '../components/bitdance/MarkdownBody.vue'
import { createPost } from '../services/community'

const router = useRouter()
const title = ref('')
const content = ref('')
const submitting = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  const t = title.value.trim()
  const c = content.value.trim()
  if (!t || !c) {
    error.value = '请填写标题与正文'
    return
  }
  submitting.value = true
  try {
    const post = await createPost(t, c)
    await router.replace(`/community/post/${post.id}`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '发布失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="new-page">
    <header class="head">
      <div>
        <h1>发布帖子</h1>
        <p>分享策略思路、实盘经验或提出问题</p>
      </div>
      <button type="button" class="ghost" @click="router.push('/community')">返回社区</button>
    </header>

    <form class="form card" @submit.prevent="submit">
      <label class="field">
        <span>标题</span>
        <input v-model="title" maxlength="200" type="text" placeholder="一句话概括" />
      </label>
      <label class="field">
        <span>正文（支持 Markdown）</span>
        <textarea v-model="content" rows="14" placeholder="支持标题、列表、代码块、表格等" />
      </label>
      <div class="field preview-field">
        <span>预览</span>
        <div class="preview-shell">
          <MarkdownBody :source="content" />
        </div>
      </div>
      <p v-if="error" class="err">{{ error }}</p>
      <div class="actions">
        <button type="submit" class="primary" :disabled="submitting">
          {{ submitting ? '发布中…' : '发布' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.new-page {
  min-height: 100vh;
  max-width: 820px;
  margin: 0 auto;
  padding: 6.8rem 1rem 2rem;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.head h1 {
  margin: 0;
  font-size: 1.45rem;
  color: var(--bq-text);
}

.head p {
  margin: 0.35rem 0 0;
  color: var(--bq-muted);
  font-size: 0.92rem;
}

.ghost {
  border: 1px solid var(--bq-edge);
  border-radius: 10px;
  padding: 0.45rem 0.75rem;
  background: transparent;
  color: var(--bq-muted);
  cursor: pointer;
}

.card {
  border-radius: 16px;
  padding: 1.1rem;
  background: linear-gradient(180deg, rgba(18, 27, 49, 0.9), rgba(11, 18, 33, 0.86));
  box-shadow:
    0 0 0 1px var(--bq-edge) inset,
    0 18px 38px rgba(0, 0, 0, 0.36);
}

.form {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: var(--bq-muted);
}

.preview-field .preview-shell {
  min-height: 120px;
  max-height: 360px;
  overflow: auto;
  border-radius: 10px;
  padding: 0.55rem 0.65rem;
  background: rgba(6, 10, 18, 0.55);
  border: 1px solid rgba(128, 152, 190, 0.15);
}

.err {
  margin: 0;
  color: #f59e9b;
  font-size: 0.88rem;
}

.actions {
  display: flex;
  justify-content: flex-end;
}

.primary {
  border: 0;
  border-radius: 10px;
  padding: 0.55rem 1rem;
  font-weight: 600;
  color: #0d0b07;
  cursor: pointer;
  background: linear-gradient(140deg, var(--bq-accent) 0%, #8f673c 100%);
}

.primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 900px) {
  .new-page {
    padding-top: 5.9rem;
  }
}
</style>
