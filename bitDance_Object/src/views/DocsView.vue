<script setup lang="ts">
import MarkdownDoc from '../components/bitdance/MarkdownDoc.vue'
import quickStart from '../content/docs/quick-start.md?raw'
import workflow from '../content/docs/workflow.md?raw'

type DocItem = {
  id: string
  title: string
  desc: string
  body: string
}

const docs: DocItem[] = [
  { id: 'quick', title: '快速开始', desc: '3 分钟跑通第一个流程', body: quickStart },
  { id: 'workflow', title: '画布工作流', desc: '从信号到执行的关键路径', body: workflow },
]
</script>

<template>
  <div class="docs-page">
    <aside class="sidenav">
      <p class="sidenav-title">文档中心</p>
      <a v-for="item in docs" :key="item.id" class="sidenav-link" :href="`#${item.id}`">
        <span>{{ item.title }}</span>
        <small>{{ item.desc }}</small>
      </a>
    </aside>

    <main class="docs-main">
      <section class="quick-grid">
        <article class="quick-card" v-for="item in docs" :key="`card-${item.id}`">
          <h2>{{ item.title }}</h2>
          <p>{{ item.desc }}</p>
          <a :href="`#${item.id}`">查看详情</a>
        </article>
      </section>

      <section v-for="item in docs" :id="item.id" :key="item.id" class="doc-section">
        <MarkdownDoc :source="item.body" />
      </section>
    </main>
  </div>
</template>

<style scoped>
.docs-page {
  min-height: 100vh;
  max-width: 1240px;
  margin: 0 auto;
  padding: 6.8rem 1rem 2rem;
  display: grid;
  gap: 0.9rem;
  grid-template-columns: 250px minmax(0, 1fr);
}

.sidenav {
  position: sticky;
  top: 6.8rem;
  align-self: start;
  border-radius: 16px;
  padding: 0.9rem;
  background: linear-gradient(180deg, rgba(18, 27, 49, 0.88), rgba(12, 19, 35, 0.84));
  box-shadow: 0 0 0 1px var(--bq-edge) inset;
}

.sidenav-title {
  margin: 0 0 0.7rem;
  color: var(--bq-accent-soft);
  font-size: 0.8rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.sidenav-link {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.65rem;
  border-radius: 10px;
  text-decoration: none;
  color: var(--bq-text);
}

.sidenav-link small {
  color: var(--bq-muted);
  font-size: 0.75rem;
}

.sidenav-link:hover {
  background: rgba(255, 255, 255, 0.05);
}

.docs-main {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.quick-grid {
  display: grid;
  gap: 0.8rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.quick-card,
.doc-section {
  border-radius: 16px;
  padding: 1rem 1.05rem;
  background: linear-gradient(180deg, rgba(18, 27, 49, 0.9), rgba(11, 18, 33, 0.86));
  box-shadow:
    0 0 0 1px var(--bq-edge) inset,
    0 18px 38px rgba(0, 0, 0, 0.36);
}

.quick-card h2 {
  margin: 0;
  color: var(--bq-text);
  font-size: 1.03rem;
}

.quick-card p {
  margin: 0.55rem 0;
  color: var(--bq-muted);
  font-size: 0.87rem;
}

.quick-card a {
  color: var(--bq-accent);
  text-decoration: none;
  font-size: 0.85rem;
}

.doc-section {
  scroll-margin-top: 6.5rem;
}

@media (max-width: 940px) {
  .docs-page {
    grid-template-columns: 1fr;
    padding-top: 5.9rem;
  }

  .sidenav {
    position: static;
  }
}

@media (max-width: 640px) {
  .quick-grid {
    grid-template-columns: 1fr;
  }
}
</style>
