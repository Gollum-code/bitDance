<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  source: string
}>()

const html = computed(() => marked.parse(props.source))
</script>

<template>
  <article class="md" v-html="html" />
</template>

<style scoped>
.md :deep(h1),
.md :deep(h2),
.md :deep(h3) {
  color: var(--bq-text);
  line-height: 1.25;
  margin: 1.2rem 0 0.65rem;
}

.md :deep(h1) {
  font-size: 1.55rem;
  margin-top: 0;
}

.md :deep(h2) {
  font-size: 1.2rem;
}

.md :deep(h3) {
  font-size: 1rem;
}

.md :deep(p),
.md :deep(li) {
  color: var(--bq-muted);
  line-height: 1.72;
}

.md :deep(ul) {
  padding-left: 1.1rem;
}

.md :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.86em;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  padding: 0.14rem 0.4rem;
  color: #efe6d8;
}

.md :deep(pre) {
  background: rgba(7, 10, 19, 0.88);
  border-radius: 12px;
  padding: 0.9rem;
  overflow-x: auto;
  box-shadow: 0 0 0 1px var(--bq-edge) inset;
}

.md :deep(pre code) {
  background: transparent;
  padding: 0;
}

.md :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-top: 0.8rem;
}

.md :deep(th),
.md :deep(td) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.09);
  padding: 0.55rem 0.45rem;
  text-align: left;
  font-size: 0.88rem;
}

.md :deep(th) {
  color: var(--bq-text);
}
</style>

