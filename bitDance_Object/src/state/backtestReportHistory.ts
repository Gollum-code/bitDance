export interface BacktestReportHistoryEntry {
  id: string
  createdAt: number
  body: string
  preview: string
  stats?: Record<string, number | string | null>
  params?: Record<string, unknown>
  /** 服务端条目常带标题，本地临时条目可为空 */
  title?: string
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

export function appendBacktestReport(
  userId: number | string,
  body: string,
  meta?: { stats?: Record<string, number | string | null>; params?: Record<string, unknown> },
): BacktestReportHistoryEntry {
  const trimmed = body.trim()
  const preview =
    trimmed.length > 200 ? `${trimmed.slice(0, 200)}…` : trimmed || '（空报告）'
  const entry: BacktestReportHistoryEntry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    createdAt: Date.now(),
    body: trimmed,
    preview,
    stats: meta?.stats,
    params: meta?.params,
  }
  const next = [entry, ...readRaw(userId)].slice(0, MAX_ITEMS)
  writeRaw(userId, next)
  return entry
}

export function removeBacktestReport(userId: number | string, id: string) {
  const next = readRaw(userId).filter((item) => item.id !== id)
  writeRaw(userId, next)
}

// ---- 服务端同步（多端一致；localStorage 仅作离线缓存） ----

import { createReport, deleteReport, listReports } from '../services/workspace'

function toLocalEntry(row: {
  id: string
  title: string
  body: string
  preview: string
  stats: Record<string, number | string | null>
  params: Record<string, unknown>
  createdAt: number
}): BacktestReportHistoryEntry {
  return {
    id: String(row.id),
    createdAt: row.createdAt * 1000, // 后端是秒，前端统一用毫秒
    body: row.body,
    preview: row.preview,
    stats: row.stats,
    params: row.params,
    title: row.title,
  }
}

/** 从服务端拉取报告历史并回写本地缓存；失败时返回本地缓存（离线降级）。 */
export async function syncReportsFromServer(userId: number | string): Promise<BacktestReportHistoryEntry[]> {
  try {
    const res = await listReports()
    const items = res.items.map(toLocalEntry).slice(0, MAX_ITEMS)
    writeRaw(userId, items)
    return items
  } catch {
    return listBacktestReports(userId)
  }
}

/** 把一条报告推到服务端，返回服务端 id（失败返回 null，不影响本地记录）。 */
export async function pushReportToServer(
  userId: number | string,
  entry: BacktestReportHistoryEntry,
): Promise<string | null> {
  try {
    const saved = await createReport({
      title: entry.title ?? '',
      body: entry.body,
      preview: entry.preview,
      stats: entry.stats ?? {},
      params: entry.params ?? {},
    })
    // 用服务端 id 替换本地临时 id，保证后续删除能命中服务端
    const next = readRaw(userId).map((item) =>
      item.id === entry.id ? toLocalEntry(saved) : item,
    )
    writeRaw(userId, next)
    return saved.id
  } catch {
    return null
  }
}

/** 同时删服务端与本地缓存。 */
export async function removeReportEverywhere(userId: number | string, id: string): Promise<void> {
  if (/^\d+$/.test(id)) {
    try {
      await deleteReport(id)
    } catch {
      /* 服务端已不存在则继续删本地 */
    }
  }
  removeBacktestReport(userId, id)
}
