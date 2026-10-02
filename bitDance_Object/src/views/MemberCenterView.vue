<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../state/auth'
import { upgradeMembershipDemo } from '../services/membership'

const router = useRouter()
const auth = useAuth()
const me = computed(() => auth.user.value)
const displayUsername = computed(() => me.value?.username || '--')
const tierLabel = computed(() =>
  me.value?.memberActive ? '会员' : me.value?.memberTier === 'member' ? '会员（已过期）' : 'Free',
)
const untilLabel = computed(() => {
  const u = me.value?.memberUntil
  if (!u) return me.value?.memberActive ? '不限期' : '--'
  try {
    return new Date(u).toLocaleString()
  } catch {
    return String(u)
  }
})

const upgrading = ref(false)
const upgradeErr = ref('')

onMounted(() => {
  void auth.init()
})

function handleLogout() {
  auth.signOut()
  router.replace('/')
}

async function handleUpgradeDemo() {
  upgradeErr.value = ''
  upgrading.value = true
  try {
    const profile = await upgradeMembershipDemo()
    auth.setSessionUser(profile)
    await auth.refresh()
  } catch (e) {
    upgradeErr.value = e instanceof Error ? e.message : '开通失败'
  } finally {
    upgrading.value = false
  }
}
</script>

<template>
  <div class="member-page">
    <header class="head">
      <div>
        <p class="eyebrow">Member Center</p>
        <h1>会员中心</h1>
        <p class="lead">
          Free 用户可使用策略列表中的首个策略；会员解锁全部策略与 AI 智能问答。
        </p>
      </div>
      <div class="head-actions">
        <button type="button" class="logout" @click="handleLogout">退出登录</button>
      </div>
    </header>

    <section class="grid">
      <article class="panel profile">
        <h2>账户概览</h2>
        <div class="kv">
          <p>用户名</p>
          <p>{{ displayUsername }}</p>
        </div>
        <div class="kv">
          <p>当前权益</p>
          <p>{{ tierLabel }}</p>
        </div>
        <div class="kv">
          <p>到期时间</p>
          <p>{{ untilLabel }}</p>
        </div>
        <div class="kv">
          <p>策略权限</p>
          <p>{{ me?.memberActive ? '全部策略' : '仅首个策略' }}</p>
        </div>
        <div class="kv">
          <p>AI 问答</p>
          <p>{{ me?.memberActive ? '已开通' : '未开通 👑' }}</p>
        </div>
      </article>

      <article class="panel plans">
        <h2>服务方案</h2>
        <div class="plan-list">
          <div class="plan" :class="{ current: !me?.memberActive }">
            <div class="plan-top">
              <h3>Free</h3>
              <p>¥0</p>
            </div>
            <ul>
              <li>社区与基础功能</li>
              <li>策略列表仅首个策略可回测</li>
              <li>不包含 AI 问答</li>
            </ul>
            <button type="button" disabled>{{ me?.memberActive ? '—' : '当前方案' }}</button>
          </div>
          <div class="plan highlight" :class="{ current: Boolean(me?.memberActive) }">
            <div class="plan-top">
              <h3>会员</h3>
              <p>演示一键开通</p>
            </div>
            <ul>
              <li>解锁策略列表中全部策略（含其余 98 个）</li>
              <li>解锁 AI 智能问答与回测报告解读</li>
              <li>后续可接入支付与订阅周期</li>
            </ul>
            <button
              v-if="!me?.memberActive"
              type="button"
              class="cta"
              :disabled="upgrading"
              @click="handleUpgradeDemo"
            >
              {{ upgrading ? '开通中…' : '开通会员（演示）' }}
            </button>
            <button v-else type="button" disabled>已是会员</button>
          </div>
        </div>
        <p v-if="upgradeErr" class="upgrade-err">{{ upgradeErr }}</p>
        <p class="hint">
          演示环境点击「开通会员」即可写入会员状态；生产环境请替换为支付回调开通接口。
        </p>
      </article>

      <article class="panel billing">
        <h2>说明</h2>
        <p class="billing-note">
          账单与支付接入后可在此展示订阅记录。当前版本仅区分 Free / 会员两类权益。
        </p>
      </article>
    </section>
  </div>
</template>

<style scoped>
.member-page {
  min-height: 100vh;
  max-width: 1240px;
  margin: 0 auto;
  padding: 6.8rem 1rem 2rem;
}

.head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.9rem;
}

.eyebrow {
  margin: 0;
  color: var(--bq-accent-soft);
  font-size: 0.76rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

h1 {
  margin: 0.42rem 0 0;
  color: var(--bq-text);
  font-size: 1.5rem;
}

.lead {
  margin: 0.55rem 0 0;
  color: var(--bq-muted);
  max-width: 52rem;
  line-height: 1.55;
}

.head-actions {
  display: inline-flex;
  gap: 0.6rem;
  align-items: center;
}

.logout {
  border: 1px solid rgba(169, 190, 221, 0.25);
  border-radius: 10px;
  padding: 0.55rem 0.85rem;
  background: rgba(18, 28, 46, 0.6);
  color: #c8d8ef;
  font-weight: 600;
  cursor: pointer;
}

.logout:hover {
  border-color: rgba(169, 190, 221, 0.4);
}

.grid {
  display: grid;
  gap: 0.9rem;
  grid-template-columns: 280px minmax(0, 1fr);
}

.panel {
  border-radius: 16px;
  padding: 0.95rem;
  background: linear-gradient(180deg, rgba(18, 27, 49, 0.9), rgba(11, 18, 33, 0.86));
  box-shadow:
    0 0 0 1px var(--bq-edge) inset,
    0 18px 38px rgba(0, 0, 0, 0.36);
}

.panel h2 {
  margin: 0;
  color: var(--bq-text);
  font-size: 1rem;
}

.profile {
  grid-row: span 2;
}

.kv {
  display: flex;
  justify-content: space-between;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  margin-top: 0.65rem;
  padding-top: 0.65rem;
  gap: 0.5rem;
}

.kv p {
  margin: 0;
  color: var(--bq-muted);
  font-size: 0.84rem;
}

.kv p:last-child {
  color: var(--bq-text);
  text-align: right;
}

.plan-list {
  margin-top: 0.75rem;
  display: grid;
  gap: 0.65rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.plan {
  border-radius: 12px;
  padding: 0.72rem;
  background: rgba(255, 255, 255, 0.03);
  box-shadow: 0 0 0 1px rgba(169, 190, 221, 0.14) inset;
}

.plan.highlight {
  box-shadow: 0 0 0 1px rgba(191, 147, 83, 0.35) inset;
  background: rgba(191, 147, 83, 0.06);
}

.plan.current {
  box-shadow: 0 0 0 1px rgba(191, 147, 83, 0.45) inset;
  background: rgba(191, 147, 83, 0.08);
}

.plan-top {
  display: flex;
  justify-content: space-between;
  gap: 0.4rem;
  align-items: baseline;
}

.plan h3 {
  margin: 0;
  color: var(--bq-text);
  font-size: 0.95rem;
}

.plan-top p {
  margin: 0;
  color: var(--bq-accent-soft);
  font-size: 0.8rem;
}

.plan ul {
  margin: 0.55rem 0 0;
  padding-left: 1rem;
  color: var(--bq-muted);
  font-size: 0.8rem;
  line-height: 1.6;
}

.plan button {
  margin-top: 0.62rem;
  width: 100%;
  border: 0;
  border-radius: 8px;
  padding: 0.45rem 0.6rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #f7f4ef;
  background: rgba(255, 255, 255, 0.1);
  cursor: pointer;
}

.plan button.cta {
  color: #0d0b07;
  background: linear-gradient(140deg, var(--bq-accent) 0%, #8f673c 100%);
}

.plan button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.plan.current button:not(:disabled) {
  color: #0d0b07;
  background: linear-gradient(140deg, var(--bq-accent) 0%, #8f673c 100%);
}

.hint {
  margin: 0.75rem 0 0;
  font-size: 0.76rem;
  color: var(--bq-muted);
  line-height: 1.5;
}

.upgrade-err {
  margin: 0.6rem 0 0;
  font-size: 0.82rem;
  color: #f59e9b;
}

.billing {
  overflow: hidden;
}

.billing-note {
  margin: 0.65rem 0 0;
  color: var(--bq-muted);
  font-size: 0.84rem;
  line-height: 1.55;
}

@media (max-width: 980px) {
  .member-page {
    padding-top: 5.9rem;
  }

  .grid {
    grid-template-columns: 1fr;
  }

  .profile {
    grid-row: auto;
  }

  .plan-list {
    grid-template-columns: 1fr;
  }
}
</style>
