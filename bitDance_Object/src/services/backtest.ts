export interface BacktestParams {
  strategyId: string
  vtSymbol: string
  start: string
  end: string
  rate: number
  slippage: number
  size: number
  pricetick: number
  capital: number
  fastWindow: number
  slowWindow: number
  signalWindow: number
  atrWindow: number
  atrMult: number
  fixedSize: number
}

export interface BacktestStats {
  start_date?: string
  end_date?: string
  total_days?: number
  total_trade_count?: number
  total_return?: number
  annual_return?: number
  sharpe_ratio?: number
  max_ddpercent?: number
  end_balance?: number
  total_net_pnl?: number
}

export interface BacktestSeries {
  dates: string[]
  balance: number[]
  drawdown: number[]
  benchmark: number[]
}

export interface BacktestTradePoint {
  date: string
  datetime?: string
  side: 'buy' | 'sell'
  action?: 'buy_open' | 'buy_close' | 'sell_open' | 'sell_close'
  price: number
  volume: number
}

/** vn.py 回测扩展：逐笔成交、FIFO 回合、信号质量、日度敞口（与后端 JSON 字段对齐） */
export interface TradeFill {
  vt_tradeid: string
  orderid: string
  tradeid: string
  datetime: string | null
  date: string | null
  direction: string
  direction_code: string | null
  offset: string
  offset_code: string | null
  price: number
  volume: number
  symbol: string
  exchange: string
  action_label: string
}

export interface TradeRound {
  side: 'long' | 'short'
  entry_datetime: string
  exit_datetime: string
  holding_days: number
  entry_price: number
  exit_price: number
  volume: number
  gross_pnl_approx: number
}

export interface SignalQuality {
  round_count: number
  breakeven_rounds?: number
  win_rate: number | null
  profit_factor: number | null
  avg_win: number | null
  avg_loss: number | null
  payoff_ratio: number | null
  expectancy_per_round: number | null
  gross_pnl_sum?: number
}

export interface DailyPositionExposure {
  date: string
  end_position: number
  close_price: number
  balance: number
  position_notional_approx: number
  position_to_equity_pct_approx: number | null
  trade_count: number
  net_pnl: number
  turnover: number
  commission: number
}

export interface DataScope {
  engine: string
  vt_symbol: string
  provided: string[]
  not_available_in_this_pipeline: string[]
  flags: { sector_concentration: boolean; margin_or_leverage: boolean }
}

export interface BacktestResult {
  success: boolean
  message: string
  params: BacktestParams & Record<string, unknown>
  stats: BacktestStats
  series: BacktestSeries
  trade_points?: BacktestTradePoint[]
  trade_fills?: TradeFill[]
  trade_rounds?: TradeRound[]
  fifo_unclosed?: { long_volume: number; short_volume: number }
  signal_quality?: SignalQuality
  daily_position_exposure?: DailyPositionExposure[]
  data_scope?: DataScope
}

export interface StrategyListItem {
  strategy_id: string
  class_name: string
  archetype: string
  source_file: string
  /** 后端标注：非会员时除首个策略外为 true */
  locked?: boolean
}

export async function listStrategies(): Promise<StrategyListItem[]> {
  const response = await fetch('/strategy/list')
  if (!response.ok) {
    throw new Error(`策略列表加载失败: ${response.status} ${response.statusText}`)
  }
  const payload = (await response.json()) as { strategies?: StrategyListItem[] }
  return payload.strategies ?? []
}

function toQueryParams(params: BacktestParams): URLSearchParams {
  const q = new URLSearchParams()
  q.set('strategy_id', params.strategyId)
  q.set('vt_symbol', params.vtSymbol)
  q.set('start', params.start)
  q.set('end', params.end)
  q.set('rate', String(params.rate))
  q.set('slippage', String(params.slippage))
  q.set('size', String(params.size))
  q.set('pricetick', String(params.pricetick))
  q.set('capital', String(params.capital))
  if (params.fastWindow != null) q.set('fast_window', String(params.fastWindow))
  if (params.slowWindow != null) q.set('slow_window', String(params.slowWindow))
  if (params.signalWindow != null) q.set('signal_window', String(params.signalWindow))
  if (params.atrWindow != null) q.set('atr_window', String(params.atrWindow))
  if (params.atrMult != null) q.set('atr_mult', String(params.atrMult))
  if (params.fixedSize != null) q.set('fixed_size', String(params.fixedSize))
  return q
}

export async function runBacktest(params: BacktestParams): Promise<BacktestResult> {
  const response = await fetch(`/strategy/${params.strategyId}?${toQueryParams(params).toString()}`)
  if (!response.ok) {
    const raw = await response.text()
    let msg = raw
    try {
      const j = JSON.parse(raw) as { message?: string; detail?: string }
      if (j?.message) msg = j.message
      else if (j?.detail) msg = String(j.detail)
    } catch {
      /* plain text */
    }
    throw new Error(msg || `回测请求失败: ${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<BacktestResult>
}
