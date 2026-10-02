import { computed, ref } from 'vue'

const loggedIn = ref(false)

export function useSessionMode() {
  const modeLabel = computed(() => (loggedIn.value ? '已登录' : '访客模式'))

  function toggleLogin() {
    loggedIn.value = !loggedIn.value
  }

  function login() {
    loggedIn.value = true
  }

  function logout() {
    loggedIn.value = false
  }

  return {
    loggedIn,
    modeLabel,
    toggleLogin,
    login,
    logout,
  }
}
