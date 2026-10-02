import type { BacktestResult } from '../services/backtest'

let lastBacktestResult: BacktestResult | null = null

export function setLastBacktestResult(result: BacktestResult | null) {
  lastBacktestResult = result
}

export function getLastBacktestResult(): BacktestResult | null {
  return lastBacktestResult
}

