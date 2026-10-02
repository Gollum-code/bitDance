<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../services/auth'
import { useAuth } from '../state/auth'

const account = ref('')
const password = ref('')
const loading = ref(false)
const errorMessage = ref('')
const router = useRouter()
const route = useRoute()
const auth = useAuth()

async function onSubmit() {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await login(account.value, password.value)
    auth.setSessionUser(data.user)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    await router.replace(redirect || '/')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <section class="auth-card">
      <p class="eyebrow">欢迎回来</p>
      <h1>登录账号</h1>
      <p class="lead">连接你的策略空间、看板与社区消息。</p>

      <form class="form" @submit.prevent="onSubmit">
        <label>
          <span>邮箱 / 用户名</span>
          <input v-model="account" type="text" placeholder="请输入邮箱或用户名" />
        </label>
        <label>
          <span>密码</span>
          <input v-model="password" type="password" placeholder="请输入密码" />
        </label>
        <button type="submit" :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
        <p v-if="errorMessage" class="err">{{ errorMessage }}</p>
      </form>

      <p class="switch">
        还没有账号？
        <RouterLink to="/register">立即注册</RouterLink>
      </p>
    </section>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 6.8rem 1rem 2rem;
}

.auth-card {
  width: min(430px, 100%);
  border-radius: 18px;
  padding: 1.2rem;
  background: linear-gradient(180deg, rgba(18, 27, 49, 0.92), rgba(11, 18, 33, 0.88));
  box-shadow:
    0 0 0 1px var(--bq-edge) inset,
    0 18px 38px rgba(0, 0, 0, 0.36);
}

.eyebrow {
  margin: 0;
  color: var(--bq-accent-soft);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-size: 0.74rem;
}

h1 {
  margin: 0.45rem 0 0;
  color: var(--bq-text);
  font-size: 1.45rem;
}

.lead {
  margin: 0.6rem 0 0;
  color: var(--bq-muted);
  font-size: 0.9rem;
}

.form {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

label span {
  color: var(--bq-muted);
  font-size: 0.81rem;
}

input {
  border: 0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--bq-text);
  padding: 0.58rem 0.7rem;
}

button {
  margin-top: 0.2rem;
  border: 0;
  border-radius: 10px;
  padding: 0.6rem;
  font-weight: 600;
  color: #0d0b07;
  background: linear-gradient(140deg, var(--bq-accent) 0%, #8f673c 100%);
}

.err {
  margin: 0.35rem 0 0;
  color: #ff8686;
  font-size: 0.82rem;
}

.switch {
  margin: 0.9rem 0 0;
  color: var(--bq-muted);
  font-size: 0.84rem;
}

.switch a {
  color: var(--bq-accent);
  text-decoration: none;
}
</style>
