<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import SiteFooter from '../components/bitdance/SiteFooter.vue'
import { useAuth } from '../state/auth'

const auth = useAuth()

const glowPos = ref({ x: 0, y: 0 })
const glowStyle = ref({ transform: 'translate3d(-9999px, -9999px, 0)' })

let rafId = 0
const target = { x: 0, y: 0 }
const current = { x: 0, y: 0 }
const GLOW_RADIUS = 600

function onMouseMove(e: MouseEvent) {
  target.x = e.clientX
  target.y = e.clientY
}

function animateGlow() {
  current.x += (target.x - current.x) * 0.08
  current.y += (target.y - current.y) * 0.08
  glowPos.value = { x: current.x, y: current.y }
  glowStyle.value = {
    transform: `translate3d(${glowPos.value.x - GLOW_RADIUS}px, ${glowPos.value.y - GLOW_RADIUS}px, 0)`,
  }
  rafId = window.requestAnimationFrame(animateGlow)
}

onMounted(() => {
  void auth.init()
  target.x = window.innerWidth * 0.5
  target.y = window.innerHeight * 0.35
  current.x = target.x
  current.y = target.y
  animateGlow()
})

onUnmounted(() => {
  window.cancelAnimationFrame(rafId)
})

const isAuthed = computed(() => auth.isAuthed.value)

function guarded(to: string) {
  return isAuthed.value ? to : { path: '/login', query: { redirect: to } }
}
</script>

<template>
  <div class="home" @mousemove="onMouseMove">
    <div class="cursor-glow" :style="glowStyle" aria-hidden="true" />
    <main class="main">
      <header class="intro">
        <h1>bitDance 策略工作台</h1>
        <p class="lead">
          当前版本聚焦：<strong>行情数据（TuShare）</strong>、<strong>策略列表与参数回测</strong>、<strong>会员权益</strong>、<strong>社区讨论</strong>，以及右下角
          <strong>bitDance AI</strong> 👑 辅助解读。
        </p>
      </header>

      <section class="actions" aria-label="功能入口">
        <RouterLink to="/market" class="card card--primary">
          <h2>行情数据</h2>
          <p>从 TuShare 拉取 A 股列表与日线 K 线，同步到本地库后一键跳转到策略回测。</p>
          <span class="card-meta">进入 →</span>
        </RouterLink>

        <RouterLink :to="guarded('/strategies')" class="card">
          <h2>我的策略</h2>
          <p>选择策略、填写回测参数并运行；回测结果会供 AI 生成报告使用。</p>
          <span class="card-meta">{{ isAuthed ? '进入' : '登录后使用' }} →</span>
        </RouterLink>

        <RouterLink to="/community" class="card">
          <h2>社区</h2>
          <p>浏览与发布帖子，交流策略思路（无需会员即可浏览部分内容）。</p>
          <span class="card-meta">进入 →</span>
        </RouterLink>

        <RouterLink :to="guarded('/member')" class="card">
          <h2>会员中心</h2>
          <p>查看账户权益、开通或续期会员；会员可解锁全部策略与 AI 问答。</p>
          <span class="card-meta">{{ isAuthed ? '进入' : '登录后查看' }} →</span>
        </RouterLink>

        <RouterLink :to="guarded('/report-history')" class="card">
          <h2>回测历史报告</h2>
          <p>查看 AI 生成的回测报告历史，支持导出 PDF；报告按账号保存在本机浏览器。</p>
          <span class="card-meta">{{ isAuthed ? '进入' : '登录后查看' }} →</span>
        </RouterLink>
      </section>

      <section class="hint" aria-label="AI 入口说明">
        <h2 class="hint-title">AI 与报告</h2>
        <p>
          登录且为会员后，点击页面右下角的 <strong>bitDance AI</strong> 打开对话面板；在「我的策略」页可点击「生成回测报告」（需已成功回测且存在成交）。
          历史报告可在首页 <strong>回测历史报告</strong> 或用户菜单中查看，并支持导出 PDF。
        </p>
      </section>

      <section v-if="!isAuthed" class="guest">
        <p>尚未登录？</p>
        <div class="guest-btns">
          <RouterLink to="/login" class="btn btn--solid">登录</RouterLink>
          <RouterLink to="/register" class="btn btn--ghost">注册</RouterLink>
        </div>
      </section>

      <SiteFooter />
    </main>
  </div>
</template>

<style scoped>
.home {
  position: relative;
  min-height: 100vh;
  padding: 5.75rem 1.25rem 2rem;
}

.cursor-glow {
  position: fixed;
  left: 0;
  top: 0;
  width: 1200px;
  height: 1200px;
  border-radius: 50%;
  pointer-events: none;
  z-index: 2;
  will-change: transform;
  background: radial-gradient(
    circle,
    rgba(255, 193, 7, 0.15) 0%,
    rgba(255, 193, 7, 0.1) 26%,
    rgba(255, 193, 7, 0.04) 48%,
    rgba(255, 193, 7, 0) 74%
  );
  filter: blur(36px);
}

@media (min-width: 768px) {
  .home {
    padding: 6rem 2rem 2.5rem;
  }
}

.main {
  position: relative;
  z-index: 3;
  max-width: 960px;
  margin: 0 auto;
}

.intro {
  margin-bottom: 2rem;
}

.intro h1 {
  margin: 0 0 0.75rem;
  font-size: clamp(1.5rem, 3.2vw, 1.85rem);
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--bq-text);
}

.lead {
  margin: 0;
  max-width: 52rem;
  font-size: 0.9375rem;
  line-height: 1.7;
  color: var(--bq-muted);
}

.lead strong {
  color: rgba(246, 250, 255, 0.92);
  font-weight: 600;
}

.actions {
  display: grid;
  gap: 1rem;
  grid-template-columns: 1fr;
}

@media (min-width: 640px) {
  .actions {
    grid-template-columns: repeat(2, 1fr);
  }
}

.card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 1.15rem 1.2rem;
  border-radius: 0.75rem;
  text-decoration: none;
  color: inherit;
  background: var(--bq-bg-panel);
  border: 1px solid var(--bq-edge);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.04) inset;
  transition:
    border-color 0.2s ease,
    background 0.2s ease;
}

.card:hover {
  border-color: rgba(191, 147, 83, 0.35);
  background: var(--bq-bg-elevated);
}

.card--primary {
  border-color: rgba(191, 147, 83, 0.28);
}

@media (min-width: 640px) {
  .card--primary {
    grid-column: span 2;
  }
}

.card h2 {
  margin: 0 0 0.45rem;
  font-size: 1rem;
  font-weight: 650;
  color: var(--bq-text);
}

.card p {
  margin: 0;
  flex: 1;
  font-size: 0.8125rem;
  line-height: 1.55;
  color: var(--bq-muted);
}

.card-meta {
  margin-top: 0.85rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--bq-accent-soft);
}

.hint {
  margin-top: 2rem;
  padding: 1rem 1.1rem;
  border-radius: 0.65rem;
  background: rgba(123, 168, 207, 0.08);
  border: 1px solid rgba(123, 168, 207, 0.2);
}

.hint-title {
  margin: 0 0 0.5rem;
  font-size: 0.875rem;
  font-weight: 650;
  color: var(--bq-cold-soft);
}

.hint p {
  margin: 0;
  font-size: 0.8125rem;
  line-height: 1.65;
  color: var(--bq-muted);
}

.hint strong {
  color: rgba(246, 250, 255, 0.9);
  font-weight: 600;
}

.guest {
  margin-top: 2rem;
  padding: 1.25rem 1.1rem;
  border-radius: 0.65rem;
  border: 1px dashed var(--bq-edge);
}

.guest p {
  margin: 0 0 0.75rem;
  font-size: 0.875rem;
  color: var(--bq-muted);
}

.guest-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border-radius: 999px;
  font-size: 0.84rem;
  font-weight: 600;
  text-decoration: none;
  transition: opacity 0.2s ease;
}

.btn--solid {
  background: linear-gradient(180deg, rgba(191, 147, 83, 0.95) 0%, #7f5731 100%);
  color: #0c0c0c;
}

.btn--ghost {
  background: rgba(255, 255, 255, 0.06);
  color: var(--bq-text);
  border: 1px solid var(--bq-edge);
}
</style>
