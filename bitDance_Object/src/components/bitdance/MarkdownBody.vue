<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = withDefaults(
  defineProps<{
    /** Markdown 源码 */
    source: string
  }>(),
  { source: '' },
)

marked.setOptions({
  gfm: true,
  breaks: true,
})

const html = computed(() => {
  const src = (props.source || '').trim()
  if (!src) return ''
  return marked.parse(src, { async: false }) as string
})
</script>

<template>
  <div class="markdown-body" v-html="html" />
</template>

<style scoped>
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 1.1rem 0 0.45rem;
  font-weight: 700;
  color: #eee8de;
  line-height: 1.35;
}
.markdown-body :deep(h1) {
  font-size: 1.35rem;
}
.markdown-body :deep(h2) {
  font-size: 1.12rem;
}
.markdown-body :deep(h3) {
  font-size: 1rem;
}
.markdown-body :deep(p) {
  margin: 0.5rem 0;
  line-height: 1.65;
  color: var(--bq-text);
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.45rem 0 0.45rem 1.1rem;
  padding: 0;
  color: var(--bq-text);
}
.markdown-body :deep(li) {
  margin: 0.2rem 0;
}
.markdown-body :deep(blockquote) {
  margin: 0.55rem 0;
  padding: 0.45rem 0.65rem;
  border-left: 3px solid rgba(191, 147, 83, 0.55);
  background: rgba(255, 255, 255, 0.04);
  color: var(--bq-muted);
}
.markdown-body :deep(hr) {
  border: 0;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  margin: 1rem 0;
}
.markdown-body :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 0.86em;
  padding: 0.12em 0.35em;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.35);
  color: #c8dcf5;
}
.markdown-body :deep(pre) {
  margin: 0.55rem 0;
  padding: 0.65rem 0.75rem;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.38);
  overflow: auto;
  max-width: 100%;
}
.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: #dbe8ff;
}
.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.65rem 0;
  font-size: 0.88rem;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0.35rem 0.45rem;
  text-align: left;
}
.markdown-body :deep(th) {
  background: rgba(255, 255, 255, 0.06);
  color: #c8d8ef;
}
.markdown-body :deep(a) {
  color: var(--bq-accent-soft);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.markdown-body :deep(img) {
  max-width: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  vertical-align: top;
  border-radius: 10px;
  margin: 0.65rem 0;
  display: block;
  box-sizing: border-box;
}
.markdown-body :deep(strong) {
  color: #f0e6d8;
}
</style>
