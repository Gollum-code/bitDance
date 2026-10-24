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
  risk_metrics?: RiskBlock
}

export interface ComparePayload {
  success: boolean
  vt_symbol: string
  start: string
  end: string
  dates: string[]
  curves: Record<string, (number | null)[]>
  results: CompareCell[]
  risk_summary?: Record<
    string,
    {
      class_name?: string
      sharpe?: number | null
      sortino?: number | null
      max_drawdown_pct?: number | null
      var_95_pct?: number | null
      risk_gate?: 'APPROVE' | 'REJECT' | null
    }
  >
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
  sortino?: number | null
  calmar?: number | null
  var_95_pct?: number | null
  cvar_95_pct?: number | null
  gate_ok?: boolean
  gate_reasons?: string[]
  trade_count?: number
}

export interface GridPayload {
  success: boolean
  strategy_id: string
  class_name?: string | null
  param_name: string
  param2?: string | null
  vt_symbol: string
  start: string
  end: string
  cells: GridCell[]
  best?: GridCell | null
  objective?: 'sharpe' | 'total_return'
  risk_gate_applied?: boolean
  risk_gate_rejected?: number
  message: string
  cached?: boolean
  mode?: '1d' | '2d'
  values?: number[]
  values2?: number[]
  matrix?: (number | null)[][]
}

export interface Grid2DBest {
  p1: number
  p2: number
  total_return?: number
  max_drawdown?: number
  sharpe?: number
  sortino?: number
  calmar?: number
  var_95_pct?: number
  trade_count?: number
}

/** 风险与绩效指标（risk_metrics 模块输出，日频口径） */
export interface RiskMetrics {
  samples: number
  active_days?: number
  active_ratio?: number
  total_return_pct: number
  annual_return_pct: number
  annual_volatility_pct: number
  sharpe_ratio: number
  sortino_ratio: number
  calmar_ratio: number
  max_drawdown_pct: number
  max_drawdown_duration_days: number
  ulcer_index_pct: number
  var_95_pct: number
  cvar_95_pct: number
  daily_win_rate: number
  profit_factor_daily: number | null
  skew: number
  excess_kurtosis: number
  risk_free_rate: number
  periods_per_year: number
  max_position_pct?: number
  avg_position_pct?: number
  exposure_days_ratio?: number
  degenerate?: boolean
  degenerate_reason?: string | null
}

export interface RiskGateCheck {
  rule: string
  value: unknown
  threshold: unknown
  passed: boolean
  desc: string
}

export interface RiskGate {
  approved: boolean
  verdict: 'APPROVE' | 'REJECT'
  reasons: string[]
  checks: RiskGateCheck[]
  limits: Record<string, number>
}

export interface MonthlyReturn {
  month: string
  return_pct: number
}

export interface RiskBlock {
  risk_metrics: RiskMetrics
  monthly_returns: MonthlyReturn[]
  risk_gate: RiskGate
  exposure?: {
    max_position_pct: number
    avg_position_pct: number
    exposure_days_ratio: number
    days: number
  }
  /** Block bootstrap 置信区间（monte_carlo 模块输出） */
  monte_carlo?: MonteCarloResult
  notes?: string[]
}

/** 单个指标的 bootstrap 分布摘要 */
export interface MonteCarloStat {
  p05: number
  p50: number
  p95: number
  mean: number
  std: number
  prob_positive: number
}

export interface MonteCarloResult {
  ok: boolean
  reason?: string
  sims?: number
  block?: number
  confidence?: number
  sample?: {
    total_return_pct: number
    annual_return_pct: number
    sharpe: number
    max_drawdown_pct: number
  }
  /** 各指标分布（百分比口径） */
  total_return?: MonteCarloStat
  annual_return?: MonteCarloStat
  /** 风险类指标：回撤深度是绝对值，越大越糟 */
  max_drawdown?: MonteCarloStat
  sharpe?: MonteCarloStat
  sharpe_ci?: [number, number]
  drawdown_p95?: number
  /** 逐日累计收益置信带（%），用于扇形图 */
  band?: { lo: number[]; mid: number[]; hi: number[] }
  interpretation?: string[]
}

/** 前向验证（walk-forward）单折结果 */
export interface WalkForwardFold {
  fold: number
  train_start: string
  train_end: string
  test_start: string
  test_end: string
  ok: boolean
  reason?: string
  best_params?: Record<string, number>
  in_sample_score?: number
  in_sample_return?: number | null
  in_sample_sharpe?: number | null
  oos_params?: Record<string, number>
  oos_score?: number | null
  oos_return?: number | null
  oos_sharpe?: number | null
  oos_max_drawdown?: number | null
  oos_trade_count?: number
  /** 样本内到样本外的退化幅度 */
  degradation?: number | null
  candidates?: number
}

export interface WalkForwardPayload {
  ok: boolean
  reason?: string
  strategy_id: string
  class_name?: string | null
  param_name: string
  values: number[]
  vt_symbol: string
  start: string
  end: string
  objective: string
  n_splits: number
  train_ratio: number
  embargo_days: number
  apply_risk_gate: boolean
  folds: WalkForwardFold[]
  in_sample_avg: number
  oos_avg: number
  oos_returns_pct: number[]
  /** 样本外 / 样本内 表现比，<0.5 视为明显过拟合 */
  efficiency_ratio: number
  consistency: number
  overfit_probability: number
  verdict: string
  message: string
}

/** 参数稳定性 / 过拟合检测 */
export interface StabilityPayload {
  ok: boolean
  reason?: string
  strategy_id: string
  class_name?: string | null
  param_name: string
  objective: string
  best_param?: number
  best_score?: number
  neighbor_avg?: number
  degradation?: number
  smoothness?: number
  /** True = 孤立尖峰，过拟合风险高 */
  isolated_peak?: boolean
  threshold?: number
  points?: number
  curve?: { param: number; score: number }[]
  verdict?: string
  vt_symbol: string
  start: string
  end: string
}

/** 因子有效性（IC / IR） */
export interface FactorIcPayload {
  success: boolean
  factor: string
  horizon: number
  lookback_days: number
  symbols: string[]
  periods: number
  ic: {
    periods: number
    ic_mean: number | null
    ic_std: number | null
    ic_ir: number | null
    t_stat: number | null
    positive_ratio: number | null
    latest_ic: number | null
    quantile_spread_avg_pct?: number | null
    verdict: string
    verdict_label: string
  }
  ic_series: number[]
  quantile?: {
    ok: boolean
    reason?: string
    quantiles?: number
    group_returns_pct?: number[]
    long_short_spread_pct?: number
    monotonicity?: number
    direction?: string
  }
  message: string
}

/** 异步回测任务 */
export interface JobInfo {
  job_id: string
  kind: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
  progress: number
  stage: string
  created_at: number
  finished_at: number | null
  elapsed_ms: number
  error: string | null
  result?: unknown
  success?: boolean
}

export interface JobStats {
  total: number
  running: number
  pending: number
  workers: number
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
  /** 名义金额模式下：区间期初价（换算股数用） */
  first_close?: number | null
  /** 名义金额模式下：换算出的股数 */
  fixed_size?: number | null
  /** 名义金额模式下：实际目标名义金额 = 期初价 × 股数 */
  target_notional?: number | null
}

export interface PortfolioWeight {
  vt_symbol: string
  weight: number
  /** 名义金额模式下：目标名义金额（元） */
  target_notional?: number
  /** 名义金额模式下：换算出的股数 */
  fixed_size?: number | null
  /** 名义金额模式下：区间期初价（用于换算股数） */
  first_close?: number | null
}

export interface PortfolioPayload {
  success: boolean
  strategy_id: string
  class_name?: string | null
  vt_symbols: string[]
  weights: PortfolioWeight[]
  start: string
  end: string
  dates: string[]
  nav: number[]
  stats?: {
    total_return?: number
    annual_return?: number
    annual_volatility_pct?: number
    max_drawdown?: number
    sharpe_ratio?: number
    sortino_ratio?: number
    calmar_ratio?: number
    var_95_pct?: number
    total_trade_count?: number
  }
  risk_metrics?: RiskMetrics
  monthly_returns?: MonthlyReturn[]
  per_symbol: PortfolioSymbolResult[]
  /** notional = 按名义金额分配（推荐）；fixed_shares = 固定股数（历史行为） */
  size_mode?: 'notional' | 'fixed_shares'
  caveat?: string
  message: string
}

export interface PaperSignal {
  date: string
  price: number
  side: string
  position_after: number
  volume?: number
  is_open?: boolean
}

export interface PaperRound {
  side: 'long' | 'short'
  entry_date: string | null
  entry_price: number
  exit_date: string
  exit_price: number
  return_pct: number
}

export interface HeatmapBucket {
  label: string
  min: number
  max: number
  count: number
}

export interface HeatmapItem {
  ts_code: string
  name: string
  pct: number
  now: number
}

export interface HeatmapPayload {
  success: boolean
  sample: number
  items: HeatmapItem[]
  buckets: HeatmapBucket[]
  breadth: { up: number; down: number; flat: number }
  message: string
}

export interface PaperPayload {
  success: boolean
  strategy_id: string
  class_name?: string
  archetype?: string
  vt_symbol: string
  position: '多' | '空' | '空仓'
  position_code: number
  entry_date?: string | null
  entry_price?: number | null
  latest_price: number
  unrealized_pct: number
  signal_count: number
  signals: PaperSignal[]
  closed_rounds?: PaperRound[]
  round_count?: number
  win_rate?: number | null
  params_used?: Record<string, unknown>
  dates: string[]
  nav: number[]
  capital: number
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
  param2?: string
  values2?: number[]
  fixed_params?: Record<string, number>
  vt_symbol?: string
  start?: string
  end?: string
  capital?: number
  objective?: 'sharpe' | 'total_return'
  apply_risk_gate?: boolean
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
  /**
   * 每个标的的目标名义金额（元）。组合等权必须用名义金额而非固定股数——
   * 一篮子标的价格从 7 元到 2300 元，固定股数会让实际权重严重偏离设定权重。
   */
  notional_per_symbol?: number[]
}): Promise<PortfolioPayload> {
  return post('/analytics/portfolio', body)
}

export function runPaper(body: {
  strategy_id: string
  vt_symbol: string
  lookback?: number
  capital?: number
  fixed_params?: Record<string, number>
}): Promise<PaperPayload> {
  return post('/analytics/paper', body)
}

export function runHeatmap(body: {
  sample?: number
  end_date?: string
}): Promise<HeatmapPayload> {
  return post('/analytics/heatmap', body)
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

// ---------------- 前向验证 / 稳定性 / 因子 IC / 异步任务 ----------------

export function runWalkForward(body: {
  strategy_id: string
  param_name: string
  values: number[]
  vt_symbol?: string
  start?: string
  end?: string
  capital?: number
  n_splits?: number
  train_ratio?: number
  embargo_days?: number
  objective?: 'sharpe' | 'total_return' | 'calmar'
  fixed_params?: Record<string, number>
  apply_risk_gate?: boolean
}): Promise<WalkForwardPayload> {
  return post('/analytics/walk-forward', body)
}

export function runStability(body: {
  strategy_id: string
  param_name: string
  values: number[]
  objective?: 'sharpe' | 'total_return' | 'calmar'
  vt_symbol?: string
  start?: string
  end?: string
  capital?: number
  neighbor_ratio?: number
  fixed_params?: Record<string, number>
}): Promise<StabilityPayload> {
  return post('/analytics/stability', body)
}

export async function runFactorIc(body: {
  vt_symbols: string[]
  factor?: string
  horizon?: number
  lookback_days?: number
  end_date?: string
}): Promise<FactorIcPayload> {
  return post('/analytics/factor-ic', body)
}

export async function getFactorUniverse(limit = 20): Promise<{ symbols: string[]; count: number }> {
  const r = await fetch(`/analytics/factor-universe?limit=${limit}`)
  if (!r.ok) throw new Error(await readError(r))
  return r.json()
}

/** 提交异步回测任务（不阻塞 HTTP 连接） */
async function submitJob<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(await readError(r))
  return r.json() as Promise<T>
}

export function submitCompareJob(body: {
  strategy_ids: string[]
  vt_symbol: string
  start: string
  end?: string
}): Promise<{ job_id: string; kind: string; status: string }> {
  return submitJob('/analytics/jobs/compare', body)
}

export function submitGridJob(body: {
  strategy_id: string
  param_name: string
  values: number[]
  param2?: string
  values2?: number[]
  fixed_params?: Record<string, number>
  vt_symbol?: string
  start?: string
  end?: string
  capital?: number
  objective?: 'sharpe' | 'total_return'
  apply_risk_gate?: boolean
}): Promise<{ job_id: string; kind: string; status: string }> {
  return submitJob('/analytics/jobs/grid', body)
}

export function submitPortfolioJob(body: {
  strategy_id: string
  vt_symbols: string[]
  weights?: number[]
  start?: string
  end?: string
  capital?: number
  fixed_params?: Record<string, number>
  notional_per_symbol?: number[]
}): Promise<{ job_id: string; kind: string; status: string }> {
  return submitJob('/analytics/jobs/portfolio', body)
}

export function submitWalkForwardJob(body: {
  strategy_id: string
  param_name: string
  values: number[]
  vt_symbol?: string
  start?: string
  end?: string
  capital?: number
  n_splits?: number
  train_ratio?: number
  embargo_days?: number
  objective?: 'sharpe' | 'total_return' | 'calmar'
  fixed_params?: Record<string, number>
  apply_risk_gate?: boolean
}): Promise<{ job_id: string; kind: string; status: string }> {
  return submitJob('/analytics/jobs/walk-forward', body)
}

export async function getJob(jobId: string): Promise<JobInfo> {
  const r = await fetch(`/analytics/jobs/${encodeURIComponent(jobId)}`)
  if (!r.ok) throw new Error(await readError(r))
  return r.json() as Promise<JobInfo>
}

export async function cancelJob(jobId: string): Promise<{ job_id: string; status: string }> {
  const r = await fetch(`/analytics/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' })
  if (!r.ok) throw new Error(await readError(r))
  return r.json() as Promise<{ job_id: string; status: string }>
}

/**
 * 轮询异步任务直到终态。
 * onUpdate 每次状态变化回调（用于进度条），onDone 拿到最终结果。
 * 返回取消函数——调用后停止轮询。
 */
export function pollJob(
  jobId: string,
  handlers: {
    onUpdate?: (info: JobInfo) => void
    onDone?: (info: JobInfo) => void
    onError?: (err: Error) => void
  },
  intervalMs = 1200,
): () => void {
  let stopped = false
  let timer: number | undefined

  const tick = async () => {
    if (stopped) return
    try {
      const info = await getJob(jobId)
      handlers.onUpdate?.(info)
      if (info.status === 'done') {
        stopped = true
        handlers.onDone?.(info)
        return
      }
      if (info.status === 'failed' || info.status === 'cancelled') {
        stopped = true
        handlers.onError?.(new Error(info.error || `任务${info.status === 'failed' ? '失败' : '已取消'}`))
        return
      }
    } catch (e) {
      handlers.onError?.(e instanceof Error ? e : new Error(String(e)))
      return
    }
    if (!stopped) {
      timer = window.setTimeout(tick, intervalMs)
    }
  }

  void tick()
  return () => {
    stopped = true
    if (timer !== undefined) window.clearTimeout(timer)
  }
}
