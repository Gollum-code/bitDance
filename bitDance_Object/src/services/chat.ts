import { getToken } from './auth'

export interface ChatSendResponse {
  success: boolean
  reply: string
  conversationId: string
}

export interface ChatStatusResponse {
  hasActiveConversation: boolean
  conversationId: string
}

function authHeaders(): HeadersInit {
  const t = getToken()
  if (!t) {
    throw new Error('请先登录')
  }
  return { Authorization: `Bearer ${t}` }
}

function ensureOk(response: Response, fallbackMessage: string) {
  if (!response.ok) {
    throw new Error(`${fallbackMessage}: ${response.status} ${response.statusText}`)
  }
}

export async function sendChatMessage(message: string): Promise<ChatSendResponse> {
  const query = new URLSearchParams({ message })
  const response = await fetch(`/api/chat/send?${query.toString()}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  ensureOk(response, '发送消息失败')
  return response.json() as Promise<ChatSendResponse>
}

export async function startNewChat(message: string): Promise<ChatSendResponse> {
  const query = new URLSearchParams({ message })
  const response = await fetch(`/api/chat/new?${query.toString()}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  ensureOk(response, '新建会话失败')
  return response.json() as Promise<ChatSendResponse>
}

export async function clearChat(): Promise<void> {
  const response = await fetch('/api/chat/clear', {
    method: 'POST',
    headers: authHeaders(),
  })
  ensureOk(response, '清空会话失败')
}

export async function getChatStatus(): Promise<ChatStatusResponse> {
  const response = await fetch('/api/chat/status', {
    headers: authHeaders(),
  })
  ensureOk(response, '查询会话状态失败')
  return response.json() as Promise<ChatStatusResponse>
}
