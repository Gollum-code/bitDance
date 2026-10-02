export interface UserDTO {
  id: number
  username: string
  email: string
  /** 账户标记：free | member */
  memberTier: 'free' | 'member'
  /** ISO 时间或 null（不限期） */
  memberUntil: string | null
  /** 当前是否享有会员权益（含未过期判断） */
  memberActive: boolean
}

export interface AuthResponse {
  token: string
  user: UserDTO
}

import { bumpAuthSession } from '../state/authSession'

const TOKEN_KEY = 'bitdance_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
  bumpAuthSession()
}

async function ensureOk(response: Response, fallbackMessage: string) {
  if (response.ok) return
  const raw = await response.text().catch(() => '')
  try {
    const payload = raw ? (JSON.parse(raw) as { message?: string }) : null
    throw new Error(payload?.message || fallbackMessage)
  } catch {
    throw new Error(raw || fallbackMessage)
  }
}

export async function register(username: string, email: string, password: string): Promise<AuthResponse> {
  const response = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password }),
  })
  await ensureOk(response, '注册失败')
  const data = (await response.json()) as AuthResponse
  setToken(data.token)
  return data
}

export async function login(account: string, password: string): Promise<AuthResponse> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account, password }),
  })
  await ensureOk(response, '登录失败')
  const data = (await response.json()) as AuthResponse
  setToken(data.token)
  return data
}

export async function fetchMe(): Promise<UserDTO> {
  const token = getToken()
  const response = await fetch('/api/auth/me', {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  await ensureOk(response, '获取用户信息失败')
  return response.json() as Promise<UserDTO>
}

export function logout() {
  setToken('')
}

