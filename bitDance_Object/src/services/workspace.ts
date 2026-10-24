import { getToken } from './auth'

export interface BacktestReportEntry {
  id: string
  title: string
  body: string
  preview: string
  stats: Record<string, number | string | null>
  params: Record<string, unknown>
  createdAt: number
}

export interface PaperPosition {
  id: number
  strategyId: string
  vtSymbol: string
  side: 'long' | 'short'
  entryPrice: number
  entryDate: string
  capital: number
  note: string
  status: 'open' | 'closed'
  exitPrice: number | null
  exitDate: string | null
  returnPct: number | null
  createdAt: number
  updatedAt: number
}

export interface AlertRule {
  id: number
  code: string
  kind: 'below' | 'above'
  value: number
  message: string
  fired: boolean
  lastFiredAt: number | null
  createdAt: number
}

export interface AlertEvent extends AlertRule {
  price: number
  name: string
  eventMessage: string
}

function authHeaders(): HeadersInit {
  return { Authorization: `Bearer ${getToken()}` }
}

async function readError(res: Response): Promise<string> {
  const raw = await res.text()
  try {
    const j = JSON.parse(raw) as { message?: string }
    if (typeof j.message === 'string') return j.message
  } catch {
    /* ignore */
  }
  return raw || `${res.status} ${res.statusText}`
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { ...init, headers: { ...authHeaders(), ...(init?.headers || {}) } })
  if (!r.ok) throw new Error(await readError(r))
  return r.json() as Promise<T>
}

// ---- 回测报告 ----

export function listReports(): Promise<{ items: BacktestReportEntry[] }> {
  return req('/api/reports')
}

export function createReport(body: {
  title?: string
  body: string
  preview?: string
  stats?: Record<string, unknown>
  params?: Record<string, unknown>
}): Promise<BacktestReportEntry> {
  return req('/api/reports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function deleteReport(id: string): Promise<{ deleted: boolean; id: string }> {
  return req(`/api/reports/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

// ---- 纸面交易持仓 ----

export function listPaperPositions(status = ''): Promise<{ items: PaperPosition[] }> {
  const q = status ? `?status=${encodeURIComponent(status)}` : ''
  return req(`/api/paper/positions${q}`)
}

export function createPaperPosition(body: {
  strategyId: string
  vtSymbol: string
  side: 'long' | 'short'
  entryPrice: number
  entryDate: string
  capital?: number
  note?: string
}): Promise<PaperPosition> {
  return req('/api/paper/positions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function closePaperPosition(
  id: number,
  body: { exitPrice: number; exitDate?: string },
): Promise<PaperPosition> {
  return req(`/api/paper/positions/${id}/close`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function deletePaperPosition(id: number): Promise<{ deleted: boolean }> {
  return req(`/api/paper/positions/${id}`, { method: 'DELETE' })
}

// ---- 价格预警 ----

export function listAlerts(): Promise<{ items: AlertRule[] }> {
  return req('/api/alerts')
}

export function createAlert(body: {
  code: string
  kind: 'below' | 'above'
  value: number
  message?: string
}): Promise<AlertRule> {
  return req('/api/alerts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function resetAlert(id: number): Promise<AlertRule> {
  return req(`/api/alerts/${id}`, { method: 'PATCH' })
}

export function deleteAlert(id: number): Promise<{ deleted: boolean }> {
  return req(`/api/alerts/${id}`, { method: 'DELETE' })
}

export function checkAlerts(): Promise<{ events: AlertEvent[]; count: number }> {
  return req('/api/alerts/check', { method: 'POST' })
}
