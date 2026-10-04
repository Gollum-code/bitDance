import type { DailyBar } from './market'

export interface CompareCell {
  ok: boolean
  strategy_id?: string
  class_name?: string
  archetype?: string
  error?: string
  trade_count?: number
  stats?: Record<string, number | string | null>
  series?: { dates: string[]; returns: number[] }
}

export interface ComparePayload {
  success: boolean
  vt_symbol: string
  start: string
  end: string
  dates: string[]
  curves: Record<string, (number | null)[]>
  results: CompareCell[]
  message: string
}

export interface ScreenItem {
  ts_code: string
  vt_symbol: string
  name: string
  close: number
  score: number
  factors: {
    mom: number
    trend: number
    volatility: number
    vol_ratio: number
    drawdown_from_high: number
  }
}

export interface ScreenPayload {
  success: boolean
  universe: number
  scanned: number
  lookback_days: number
  items: ScreenItem[]
  factors_used: string[]
  message: string
}

export interface GridCell {
  value: number
  ok: boolean
  error?: string
  total_return?: number | null
  annual_return?: number | null
  max_drawdown?: number | null
  sharpe?: number | null
  trade_count?: number
}

export interface GridPayload {
  success: boolean
  strategy_id: string
  class_name?: string | null
  param_name: string
  vt_symbol: string
  start: string
  end: string
  cells: GridCell[]
  best?: GridCell | null
  message: string
  cached?: boolean
}

export interface RealtimeQuote {
  [key: string]: unknown
}

export interface PortfolioSymbolResult {
  vt_symbol: string
  ok: boolean
  error?: string
  class_name?: string
  total_return?: number
  trade_count?: number
}

export interface PortfolioPayload {
  success: boolean
  strategy_id: string
  class_name?: string | null
  vt_symbols: string[]
  weights: { vt_symbol: string; weight: number }[]
  start: string
  end: string
  dates: string[]
  nav: number[]
  stats?: {
    total_return?: number
    annual_return?: number
    max_drawdown?: number
    sharpe_ratio?: number
    total_trade_count?: number
  }
  per_symbol: PortfolioSymbolResult[]
  message: string
}

async function readError(res: Response): Promise<string> {
  const raw = await res.text()
  try {
    const j = JSON.parse(raw) as { detail?: unknown; message?: string }
    if (typeof j.detail === 'string') return j.detail
    if (typeof j.message === 'string') return j.message
  } catch {
    /* ignore */
  }
  return raw || `${res.status} ${res.statusText}`
}

function post<T>(path: string, body: unknown): Promise<T> {
  return fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(async (r) => {
    if (!r.ok) throw new Error(await readError(r))
    return r.json() as Promise<T>
  })
}

export function runCompare(body: {
  strategy_ids: string[]
  vt_symbol: string
  start: string
  end?: string
}): Promise<ComparePayload> {
  return post('/analytics/compare', body)
}

export function runScreen(body: {
  universe_limit?: number
  top_n?: number
  lookback_days?: number
  end_date?: string
}): Promise<ScreenPayload> {
  return post('/analytics/screen', body)
}

export function runGrid(body: {
  strategy_id: string
  param_name: string
  values: number[]
  fixed_params?: Record<string, number>
  vt_symbol?: string
  start?: string
  end?: string
  capital?: number
}): Promise<GridPayload> {
  return post('/analytics/grid', body)
}

export function runPortfolio(body: {
  strategy_id: string
  vt_symbols: string[]
  weights?: number[]
  start?: string
  end?: string
  capital?: number
  fixed_params?: Record<string, number>
}): Promise<PortfolioPayload> {
  return post('/analytics/portfolio', body)
}

export async function getRealtime(symbols: string[]): Promise<{ items: RealtimeQuote[]; count: number }> {
  const r = await fetch(`/analytics/realtime?symbols=${encodeURIComponent(symbols.join(','))}`)
  if (!r.ok) throw new Error(await readError(r))
  return r.json()
}

export function openRealtimeWs(symbols: string[], onMessage: (items: RealtimeQuote[]) => void): () => void {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  let closed = false
  let timer: number | undefined
  let reconnectTimer: number | undefined
  let current: WebSocket | null = null

  const connect = () => {
    if (closed) return
    const ws = new WebSocket(`${proto}//${window.location.host}/analytics/ws`)
    current = ws
    ws.onopen = () => {
      ws.send(JSON.stringify({ symbols }))
      timer = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ symbols }))
      }, 60000)
    }
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data as string) as { items?: RealtimeQuote[] }
        if (data.items) onMessage(data.items)
      } catch {
        /* ignore */
      }
    }
    ws.onclose = () => {
      if (timer !== undefined) window.clearInterval(timer)
      if (!closed) {
        reconnectTimer = window.setTimeout(connect, 5000)
      }
    }
  }
  connect()

  return () => {
    closed = true
    if (timer !== undefined) window.clearInterval(timer)
    if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
    current?.close()
    current = null
  }
}

export interface DailyBarEx extends DailyBar {
  __name?: string
}
