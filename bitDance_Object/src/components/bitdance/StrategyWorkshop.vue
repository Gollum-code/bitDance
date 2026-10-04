<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { listStrategies, type StrategyListItem } from '../../services/backtest'
import { STRATEGY_ARCHETYPE_LABEL, STRATEGY_DISPLAY_NAMES } from '../../data/strategyDisplayNames'

const loading = ref(true)
const errorText = ref('')
const strategies = ref<StrategyListItem[]>([])

// 按 archetype 归类（族名 -> 中文标签 -> 数量），展示真实的策略谱系
const families = computed(() => {
  const groups = new Map<string, { label: string; items: StrategyListItem[] }>()
  for (const it of strategies.value) {
    const arch = it.archetype || 'other'
    const label = STRATEGY_ARCHETYPE_LABEL[arch] ?? arch
    if (!groups.has(arch)) groups.set(arch, { label, items: [] })
    groups.get(arch)!.items.push(it)
  }
  return [...groups.entries()]
    .map(([key, g]) => ({ key, label: g.label, count: g.items.length, items: g.items }))
    .sort((a, b) => b.count - a.count)
})

const tierOf = (idx: number) => ['primary', 'secondary', 'tertiary', 'quaternary'][Math.min(idx, 3)]

function displayName(id: string) {
  return STRATEGY_DISPLAY_NAMES[id] ?? id
}

const risk = ref('12')
const freq = ref('中频')
const slip = ref('0.8')

onMounted(async () => {
  try {
    strategies.value = await listStrategies()
  } catch (e) {
    errorText.value = e instanceof Error ? e.message : '策略列表加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section id="workshop" class="workshop" aria-labelledby="workshop-title">
    <div class="panel">
      <h2 id="workshop-title" class="sr-only">策略工作台</h2>
      <div class="timeline">
        <p class="eyebrow">策略谱系</p>
        <p v-if="loading" class="meta">策略加载中…</p>
        <p v-else-if="errorText" class="meta">未登录无法加载策略：{{ errorText }}</p>
        <ul v-else class="stack">
          <li
            v-for="(f, i) in families"
            :key="f.key"
            :class="['row', tierOf(i)]"
          >
            <span class="name">
              {{ f.label }}
              <span class="count">{{ f.count }} 个策略</span>
            </span>
            <span class="meta">
              包含：
              <template v-for="(it, k) in f.items.slice(0, 3)" :key="it.strategy_id">
                {{ k > 0 ? '、' : '' }}{{ displayName(it.strategy_id) }}
              </template>
              <template v-if="f.items.length > 3"> 等 {{ f.items.length }} 个</template>
            </span>
          </li>
        </ul>
        <RouterLink to="/strategies" class="enter-link">进入策略工作台 →</RouterLink>
      </div>

      <div class="config">
        <p class="eyebrow">参数</p>
        <label class="field">
          <span class="field-label">风险预算 (%)</span>
          <span class="field-line">
            <input v-model="risk" type="text" class="underline-input" autocomplete="off" />
          </span>
        </label>
        <label class="field">
          <span class="field-label">调仓频率</span>
          <span class="field-line">
            <input v-model="freq" type="text" class="underline-input" autocomplete="off" />
          </span>
        </label>
        <label class="field">
          <span class="field-label">滑点假设 (bp)</span>
          <span class="field-line">
            <input v-model="slip" type="text" class="underline-input" autocomplete="off" />
          </span>
        </label>
      </div>
    </div>
  </section>
</template>

<style scoped>
.workshop {
  margin-top: 3rem;
  scroll-margin-top: 6rem;
}

.panel {
  display: grid;
  gap: 2rem;
  padding: 1.75rem 1.5rem;
  border-radius: 1.25rem;
  background: #040404;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.028) inset,
    0 -1px 0 0 rgba(191, 147, 83, 0.1) inset,
    0 28px 60px rgba(0, 0, 0, 0.55),
    -1px -1px 0 0 rgba(191, 147, 83, 0.12);
}

@media (min-width: 900px) {
  .panel {
    grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
    align-items: start;
  }
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.eyebrow {
  margin: 0 0 1rem;
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: rgba(191, 147, 83, 0.45);
}

.stack {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.row {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.name {
  display: block;
  line-height: 1.35;
  color: rgba(245, 245, 244, 0.92);
}

.meta {
  font-size: 0.75rem;
  color: rgba(168, 162, 158, 0.55);
  line-height: 1.5;
}

.count {
  font-size: 0.72rem;
  font-weight: 500;
  color: rgba(191, 147, 83, 0.75);
  margin-left: 0.35rem;
}

.enter-link {
  display: inline-block;
  margin-top: 0.9rem;
  font-size: 0.8125rem;
  color: rgba(191, 147, 83, 0.92);
  text-decoration: none;
}

.enter-link:hover {
  text-decoration: underline;
}

.primary .name {
  font-weight: 700;
  font-size: 1.05rem;
  letter-spacing: -0.02em;
}

.secondary .name {
  font-weight: 600;
  font-size: 0.95rem;
}

.tertiary .name {
  font-weight: 500;
  font-size: 0.9rem;
  color: rgba(231, 229, 228, 0.78);
}

.quaternary .name {
  font-weight: 300;
  font-size: 0.88rem;
  color: rgba(168, 162, 158, 0.72);
}

.config {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field-label {
  font-size: 0.75rem;
  color: rgba(168, 162, 158, 0.65);
}

.field-line {
  position: relative;
  display: block;
}

.field-line::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: rgba(68, 64, 60, 0.55);
  pointer-events: none;
}

.field-line::before {
  content: '';
  position: absolute;
  left: 50%;
  bottom: 0;
  width: 0;
  height: 1px;
  transform: translateX(-50%);
  background: linear-gradient(
    90deg,
    transparent,
    rgba(191, 147, 83, 0.15) 15%,
    rgba(191, 147, 83, 0.95) 50%,
    rgba(191, 147, 83, 0.15) 85%,
    transparent
  );
  box-shadow: 0 0 12px rgba(191, 147, 83, 0.35);
  transition: width 0.45s cubic-bezier(0.22, 1, 0.36, 1);
  pointer-events: none;
  z-index: 1;
}

.field:focus-within .field-line::before {
  width: 100%;
}

.underline-input {
  width: 100%;
  padding: 0.35rem 0;
  border: none;
  background: transparent;
  font-size: 0.9375rem;
  color: rgba(250, 250, 249, 0.95);
  outline: none;
}

.underline-input::placeholder {
  color: rgba(120, 113, 108, 0.65);
}
</style>

