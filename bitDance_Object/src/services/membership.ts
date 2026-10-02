import type { UserDTO } from './auth'
import { getToken } from './auth'

export async function upgradeMembershipDemo(): Promise<UserDTO> {
  const token = getToken()
  if (!token) {
    throw new Error('请先登录')
  }
  const response = await fetch('/api/membership/upgrade-demo', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    const raw = await response.text().catch(() => '')
    let msg = raw
    try {
      const j = JSON.parse(raw) as { message?: string }
      if (j?.message) msg = j.message
    } catch {
      /* ignore */
    }
    throw new Error(msg || `开通失败: ${response.status}`)
  }
  return response.json() as Promise<UserDTO>
}
