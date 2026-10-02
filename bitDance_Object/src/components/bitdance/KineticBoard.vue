<script setup lang="ts">
import { onMounted, ref } from 'vue'

type Metric = {
  id: string
  label: string
  value: string
  hint: string
  /** vertical offset for stagger */
  lift: string
}

const metrics = ref<Metric[]>([
  { id: '1', label: '市场情绪温度', value: '62 / 100', hint: '由波动率、成交与新闻流共振计算', lift: '0' },
  { id: '2', label: '全市场成交额', value: '1.07 万亿', hint: 'A 股当日实时聚合', lift: '1.25rem' },
  { id: '3', label: '量化策略活跃度', value: '74%', hint: '样本池策略在线率', lift: '0.5rem' },
  { id: '4', label: '异常波动事件', value: '5', hint: '近 24h 自动标记', lift: '1.75rem' },
])

const visible = ref(false)

onMounted(() => {
  requestAnimationFrame(() => {
    visible.value = true
  })
})

function refreshValues() {
  const sentiment = Math.round(55 + Math.random() * 30)
  const turnover = (0.85 + Math.random() * 0.45).toFixed(2)
  const activity = `${Math.round(62 + Math.random() * 26)}%`
  const anomaly = `${Math.round(2 + Math.random() * 6)}`

  metrics.value = metrics.value.map((m) => {
    if (m.id === '1') return { ...m, value: `${sentiment} / 100` }
    if (m.id === '2') return { ...m, value: `${turnover} 万亿` }
    if (m.id === '3') return { ...m, value: activity }
    if (m.id === '4') return { ...m, value: anomaly }
    return m
  })
}

defineExpose({ refreshValues })
</script>

<template>
  <section id="dashboard" class="kinetic" aria-labelledby="kinetic-heading">
    <div class="kinetic-head">
      <h2 id="kinetic-heading" class="title">公共脉冲看板</h2>
      <p class="sub">未登录状态仅展示公共市场信号，个人资产与订单将在鉴权后解锁。</p>
    </div>

    <TransitionGroup v-if="visible" name="card" tag="div" class="stagger">
      <article
        v-for="m in metrics"
        :key="m.id"
        class="depth-card"
        :style="{ marginTop: m.lift }"
      >
        <p class="label">{{ m.label }}</p>
        <div class="value-row">
          <Transition name="rise" mode="out-in">
            <span :key="m.value" class="value">{{ m.value }}</span>
          </Transition>
        </div>
        <p class="hint">{{ m.hint }}</p>
      </article>
    </TransitionGroup>
  </section>
</template>

<style scoped>
.kinetic {
  margin-top: 2.5rem;
  scroll-margin-top: 6rem;
}

.kinetic-head {
  margin-bottom: 1.75rem;
  max-width: 36rem;
}

.title {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(191, 147, 83, 0.55);
}

.sub {
  margin: 0.5rem 0 0;
  font-size: 0.875rem;
  line-height: 1.55;
  color: rgba(168, 162, 158, 0.75);
}

.stagger {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 1rem 1.25rem;
}

@media (min-width: 768px) {
  .stagger {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1100px) {
  .stagger {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    align-items: start;
  }
}

/* Infinite depth: 1% darker than #050505 → ~#040404 */
.depth-card {
  position: relative;
  border-radius: 1rem;
  padding: 1.25rem 1.35rem;
  background: #040404;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.03) inset,
    0 -1px 0 0 rgba(191, 147, 83, 0.12) inset,
    0 24px 48px rgba(0, 0, 0, 0.55),
    -1px -1px 0 0 rgba(191, 147, 83, 0.14);
  overflow: hidden;
}

.depth-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  background: linear-gradient(
    145deg,
    rgba(191, 147, 83, 0.09) 0%,
    transparent 42%,
    transparent 100%
  );
  opacity: 0.9;
}

.label {
  margin: 0;
  font-size: 0.6875rem;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(168, 162, 158, 0.55);
}

.value-row {
  margin-top: 0.65rem;
  min-height: 2.25rem;
}

.value {
  display: inline-block;
  font-size: 1.5rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  color: rgba(250, 250, 249, 0.96);
}

.hint {
  margin: 0.45rem 0 0;
  font-size: 0.75rem;
  color: rgba(168, 162, 158, 0.65);
}

.rise-enter-active,
.rise-leave-active {
  transition:
    opacity 0.5s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.55s cubic-bezier(0.22, 1, 0.36, 1);
}

.rise-enter-from {
  opacity: 0;
  transform: translateY(14px);
}

.rise-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.card-enter-active {
  transition:
    opacity 0.7s ease,
    transform 0.8s cubic-bezier(0.22, 1, 0.36, 1);
}

.card-enter-from {
  opacity: 0;
  transform: translateY(22px);
}

.card-leave-active {
  transition: opacity 0.35s ease;
}

.card-leave-to {
  opacity: 0;
}
</style>

