import { computed, ref } from 'vue'
import type { UserDTO } from '../services/auth'
import { fetchMe, getToken, logout as clearToken } from '../services/auth'
import { authSessionEpoch } from './authSession'

const user = ref<UserDTO | null>(null)
const ready = ref(false)

export function useAuth() {
  const currentUser = computed(() => user.value)
  const isAuthed = computed(() => {
    authSessionEpoch.value
    return !!getToken()
  })
  const isReady = computed(() => ready.value)

  async function init() {
    const token = getToken()
    if (!token) {
      user.value = null
      ready.value = true
      return
    }
    if (user.value) {
      ready.value = true
      return
    }
    try {
      user.value = await fetchMe()
    } catch {
      clearToken()
      user.value = null
    }
    ready.value = true
  }

  async function refresh() {
    const token = getToken()
    if (!token) {
      user.value = null
      return
    }
    user.value = await fetchMe()
  }

  function setSessionUser(profile: UserDTO | null) {
    user.value = profile
    ready.value = true
  }

  function signOut() {
    clearToken()
    user.value = null
  }

  return {
    user: currentUser,
    ready: isReady,
    isAuthed,
    init,
    refresh,
    setSessionUser,
    signOut,
  }
}

