import type { BacktestParams, BacktestResult } from './backtest'
import { createPost, type PostDetailDTO } from './community'

export const SHARE_TITLE_MAX = 200
/** 与 Spring CreatePostRequest content @Size 对齐 */
export const SHARE_CONTENT_MAX = 15_000_000

function clampTitle(s: string): string {
  const t = s.trim()
  if (t.length <= SHARE_TITLE_MAX) return t
  return `${t.slice(0, SHARE_TITLE_MAX - 3)}...`
}

function row(label: string, value: string | number | undefined | null): string {
  const v = value === undefined || value === null ? '—' : String(value)
  return `| ${label} | ${v} |`
}

function formatNum(n: number): string {
  if (Number.isNaN(n)) return '—'
  return Number.isInteger(n) ? String(n) : n.toFixed(4).replace(/\.?0+$/, '')
}

/** 默认标题（用户可在弹窗中覆盖） */
export function defaultStrategyShareTitle(p: BacktestParams): string {
  return clampTitle(`[回测分享] 策略 ${p.strategyId} · ${p.vtSymbol} · ${p.start} ~ ${p.end}`)
}

function buildSeriesTailMarkdown(r: BacktestResult, maxRows: number): string {
  const s = r.series
  if (!s?.dates?.length) return ''
  const n = s.dates.length
  const start = Math.max(0, n - maxRows)
  const bal = s.balance ?? []
  const dd = s.drawdown ?? []
  const bm = (s.benchmark ?? []) as number[]
  const lines: string[] = []
  lines.push('## 回测数据（权益序列抽样，最近若干交易日）')
  lines.push('')
  lines.push('| 日期 | 权益 | 回撤 | 基准涨跌(%) |')
  lines.push('| --- | --- | --- | --- |')
  for (let i = start; i < n; i++) {
    const d = s.dates[i] ?? '—'
    const b = typeof bal[i] === 'number' ? bal[i].toFixed(2) : '—'
    const dv = typeof dd[i] === 'number' ? dd[i].toFixed(2) : '—'
    const bv = typeof bm[i] === 'number' ? bm[i].toFixed(4) : '—'
    lines.push(`| ${d} | ${b} | ${dv} | ${bv} |`)
  }
  lines.push('')
  lines.push(`*共 ${n} 个交易日，上表展示最后 ${n - start} 行。*`)
  return lines.join('\n')
}

export interface StrategyShareChartUrls {
  performance?: string
  drawdown?: string
}

export interface BuildStrategyShareMarkdownInput {
  /** 用户简介，置于文首 */
  intro?: string
  params: BacktestParams
  result: BacktestResult
  strategyDisplayLine: string
  chartUrls?: StrategyShareChartUrls
  /** 权益表尾部行数 */
  seriesTailRows?: number
}

/**
 * 完整 Markdown：简介 + 策略 + 参数 + 绩效 + 数据表 + 图表
 */
export function buildStrategyShareMarkdown(input: BuildStrategyShareMarkdownInput): string {
  const { intro, params: p, result: r, strategyDisplayLine, chartUrls, seriesTailRows = 40 } = input
  const lines: string[] = []

  const introTrim = (intro || '').trim()
  if (introTrim) {
    lines.push('## 简介')
    lines.push('')
    lines.push(introTrim)
    lines.push('')
  }

  lines.push('> 本文由 **bitDance 策略工作台** 根据回测参数与结果生成（含图表与数据抽样）。')
  lines.push('')
  lines.push('## 策略')
  lines.push(strategyDisplayLine)
  lines.push('')
  lines.push('## 回测参数')
  lines.push('| 项 | 值 |')
  lines.push('| --- | --- |')
  lines.push(row('标的 vtSymbol', p.vtSymbol))
  lines.push(row('区间', `${p.start} ~ ${p.end}`))
  lines.push(row('手续费率 rate', p.rate))
  lines.push(row('滑点 slippage', p.slippage))
  lines.push(row('合约乘数 size', p.size))
  lines.push(row('最小跳动 pricetick', p.pricetick))
  lines.push(row('初始资金 capital', p.capital))
  lines.push(row('fast / slow / signal 窗口', `${p.fastWindow} / ${p.slowWindow} / ${p.signalWindow}`))
  lines.push(row('ATR 窗口 / 倍数', `${p.atrWindow} / ${p.atrMult}`))
  lines.push(row('每次手数 fixedSize', p.fixedSize))
  lines.push('')
  lines.push('## 回测结果摘要')
  lines.push(`- **success**: ${r.success ? '是' : '否'}`)
  lines.push(`- **message**: ${r.message || '—'}`)
  const st = r.stats
  if (st && Object.keys(st).length > 0) {
    lines.push('')
    lines.push('| 指标 | 数值 |')
    lines.push('| --- | --- |')
    if (st.total_return != null) lines.push(row('总收益率 %', formatNum(st.total_return)))
    if (st.annual_return != null) lines.push(row('年化收益率 %', formatNum(st.annual_return)))
    if (st.sharpe_ratio != null) lines.push(row('夏普比率', formatNum(st.sharpe_ratio)))
    if (st.max_ddpercent != null) lines.push(row('最大回撤 %', formatNum(st.max_ddpercent)))
    if (st.total_trade_count != null) lines.push(row('成交笔数', st.total_trade_count))
    if (st.end_balance != null) lines.push(row('期末权益', formatNum(st.end_balance)))
    if (st.total_net_pnl != null) lines.push(row('净利润', formatNum(st.total_net_pnl)))
  }
  const seriesMd = buildSeriesTailMarkdown(r, seriesTailRows)
  if (seriesMd) {
    lines.push('')
    lines.push(seriesMd)
  }

  const perf = chartUrls?.performance?.trim()
  const dd = chartUrls?.drawdown?.trim()
  if (perf || dd) {
    lines.push('')
    lines.push('## 图表（工作台导出，标题与图例已包含在图中）')
    lines.push('')
    if (perf) {
      lines.push(`![](${perf})`)
      lines.push('')
    }
    if (dd) {
      lines.push(`![](${dd})`)
      lines.push('')
    }
  }

  lines.push('')
  lines.push('---')
  lines.push('*更多逐笔成交、FIFO 回合明细等见工作台回测 JSON 响应字段 `trade_fills` / `trade_rounds` 等。*')

  let body = lines.join('\n')
  if (body.length > SHARE_CONTENT_MAX) {
    body = `${body.slice(0, SHARE_CONTENT_MAX - 120)}\n\n…（正文超过上限已截断，请缩短简介或降低图表分辨率后重试）`
  }
  return body
}

export interface PublishStrategyShareInput extends BuildStrategyShareMarkdownInput {
  title: string
}

export async function publishStrategyShare(input: PublishStrategyShareInput): Promise<PostDetailDTO> {
  const title = clampTitle(input.title.trim() || defaultStrategyShareTitle(input.params))
  const content = buildStrategyShareMarkdown(input)
  if (content.length > SHARE_CONTENT_MAX) {
    throw new Error(`正文过长（${content.length} 字符），请缩短简介或稍后重试`)
  }
  return createPost(title, content)
}
