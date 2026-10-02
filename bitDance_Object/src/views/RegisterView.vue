<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { register } from '../services/auth'
import { useAuth } from '../state/auth'

const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const errorMessage = ref('')
const router = useRouter()
const auth = useAuth()

async function onSubmit() {
  errorMessage.value = ''
  if (password.value !== confirmPassword.value) {
    errorMessage.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    const data = await register(username.value, email.value, password.value)
    auth.setSessionUser(data.user)
    await router.replace('/')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <section class="auth-card">
      <p class="eyebrow">创建账户</p>
      <h1>注册 bitDance</h1>
      <p class="lead">开通后可保存策略、同步看板偏好和订阅社区动态。</p>

      <form class="form" @submit.prevent="onSubmit">
        <label>
          <span>用户名</span>
          <input v-model="username" type="text" placeholder="请输入用户名" />
        </label>
        <label>
          <span>邮箱</span>
          <input v-model="email" type="email" placeholder="请输入邮箱" />
        </label>
        <label>
          <span>密码</span>
          <input v-model="password" type="password" placeholder="请输入密码" />
        </label>
        <label>
          <span>确认密码</span>
          <input v-model="confirmPassword" type="password" placeholder="请再次输入密码" />
        </label>
        <button type="submit" :disabled="loading">{{ loading ? '创建中...' : '创建账号' }}</button>
        <p v-if="errorMessage" class="err">{{ errorMessage }}</p>
      </form>

      <p class="switch">
        已有账号？
        <RouterLink to="/login">去登录</RouterLink>
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
  width: min(460px, 100%);
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
