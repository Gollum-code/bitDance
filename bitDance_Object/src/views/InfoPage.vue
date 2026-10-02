<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => (route.meta.title as string) ?? 'bitDance')
</script>

<template>
  <div class="page">
    <section class="card">
      <p class="eyebrow">模块建设中</p>
      <h1 class="title">{{ title }}</h1>
      <p class="lead">该页面将沿用 bitDance 新的策略工作流视觉体系。当前可先体验首页与策略构建页。</p>
      <RouterLink to="/" class="back">返回首页</RouterLink>
    </section>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; display: grid; place-items: center; padding: 7rem 1.2rem 3rem; }
.card {
  width: min(34rem, 100%);
  padding: 2rem;
  border-radius: 1rem;
  background: var(--bq-bg-elevated);
  box-shadow: 0 0 0 1px var(--bq-edge) inset, 0 20px 60px rgba(0,0,0,.45);
}
.eyebrow { margin: 0; font-size: .7rem; letter-spacing: .2em; text-transform: uppercase; color: var(--bq-accent-soft); }
.title { margin: .6rem 0 0; font-size: 1.5rem; color: var(--bq-text); }
.lead { margin: .8rem 0 0; line-height: 1.7; color: var(--bq-muted); }
.back { margin-top: 1.3rem; display: inline-flex; color: var(--bq-accent); text-decoration: none; }
</style>
