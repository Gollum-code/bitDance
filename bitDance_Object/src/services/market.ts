export interface StockBasicItem {
  ts_code: string
  symbol: string
  name: string
  area?: string
  industry?: string
  list_date?: string
  vt_symbol: string
}

export interface DailyBar {
  date: string
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  vol: number
  amount: number
}

export interface DailyPayload {
  ts_code: string
  vt_symbol: string
  bars: DailyBar[]
  last?: DailyBar | null
  message?: string
}

async function readError(res: Response): Promise<string> {
  const raw = await res.text()
  try {
    const j = JSON.parse(raw) as { detail?: unknown; message?: string }
    if (typeof j.detail === 'string') return j.detail
    if (Array.isArray(j.detail)) {
      const parts = j.detail.map((x) => (typeof x === 'object' && x && 'msg' in x ? String((x as { msg: unknown }).msg) : String(x)))
      return parts.join('; ')
    }
    if (typeof j.message === 'string') return j.message
  } catch {
    /* ignore */
  }
  return raw || `${res.status} ${res.statusText}`
}

export async function listMarketStocks(q?: string, limit = 80): Promise<{ items: StockBasicItem[]; count?: number }> {
  const params = new URLSearchParams()
  if (q?.trim()) params.set('q', q.trim())
  params.set('limit', String(limit))
  const r = await fetch(`/api/market/stocks?${params.toString()}`)
  if (!r.ok) throw new Error(await readError(r))
  return r.json()
}

export async function getMarketDaily(ts_code: string, start_date: string, end_date: string): Promise<DailyPayload> {
  const params = new URLSearchParams({
    ts_code,
    start_date,
    end_date,
  })
  const r = await fetch(`/api/market/daily?${params.toString()}`)
  if (!r.ok) throw new Error(await readError(r))
  return r.json()
}

export async function syncMarketToVnpy(
  ts_code: string,
  start_date: string,
  end_date: string,
): Promise<{ status?: string; vt_symbol?: string; imported_count?: number; message?: string }> {
  const r = await fetch('/api/market/sync-vnpy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ts_code, start_date, end_date }),
  })
  if (!r.ok) throw new Error(await readError(r))
  return r.json()
}

export async function uploadCsvToVnpy(
  file: File,
): Promise<{ status?: string; imported_count?: number; message?: string }> {
  const form = new FormData()
  form.append('file', file)
  const r = await fetch('/api/tusharestaticsupload/upload/csv', {
    method: 'POST',
    body: form,
  })
  if (!r.ok) throw new Error(await readError(r))
  return r.json()
}

export function defaultChartEndDate(): string {
  return new Date().toISOString().slice(0, 10)
}

export function defaultChartStartDate(yearsBack = 2): string {
  const d = new Date()
  d.setFullYear(d.getFullYear() - yearsBack)
  return d.toISOString().slice(0, 10)
}
