import { ref } from 'vue'

/** 递增以使依赖 localStorage token 的 computed（如 isAuthed）在登录/登出后更新 */
export const authSessionEpoch = ref(0)

export function bumpAuthSession() {
  authSessionEpoch.value += 1
}
