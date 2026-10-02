export interface BacktestReportHistoryEntry {
  id: string
  createdAt: number
  body: string
  preview: string
}

const MAX_ITEMS = 80

function keyForUser(userId: number | string) {
  return `bitdance_backtest_reports_${userId}`
}

function readRaw(userId: number | string): BacktestReportHistoryEntry[] {
  try {
    const raw = localStorage.getItem(keyForUser(userId))
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (item): item is BacktestReportHistoryEntry =>
        typeof item === 'object' &&
        item !== null &&
        typeof (item as BacktestReportHistoryEntry).id === 'string' &&
        typeof (item as BacktestReportHistoryEntry).body === 'string',
    )
  } catch {
    return []
  }
}

function writeRaw(userId: number | string, items: BacktestReportHistoryEntry[]) {
  localStorage.setItem(keyForUser(userId), JSON.stringify(items))
}

export function listBacktestReports(userId: number | string): BacktestReportHistoryEntry[] {
  return readRaw(userId).sort((a, b) => b.createdAt - a.createdAt)
}

export function appendBacktestReport(userId: number | string, body: string): BacktestReportHistoryEntry {
  const trimmed = body.trim()
  const preview =
    trimmed.length > 200 ? `${trimmed.slice(0, 200)}…` : trimmed || '（空报告）'
  const entry: BacktestReportHistoryEntry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    createdAt: Date.now(),
    body: trimmed,
    preview,
  }
  const next = [entry, ...readRaw(userId)].slice(0, MAX_ITEMS)
  writeRaw(userId, next)
  return entry
}

export function removeBacktestReport(userId: number | string, id: string) {
  const next = readRaw(userId).filter((item) => item.id !== id)
  writeRaw(userId, next)
}
