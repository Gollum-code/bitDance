import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..', '..')
const dir = process.env.STRATEGY_TEMPLATE_DIR || 'D:\\量化交易\\量化投资策略源码模型多因子短线量化交易策略方法分析电子版模板\\量化投资策略源码模型多因子短线量化交易策略方法分析电子版模板\\量化策略代码(99份)'
const outPath = path.join(__dirname, '..', 'src', 'data', 'strategyDisplayNames.ts')

const files = fs.readdirSync(dir).filter((f) => f.endsWith('.py') || f.endsWith('.txt'))
const m = {}
for (const f of files) {
  const base = f.replace(/\.(py|txt)$/, '')
  const mm = String(base).match(/^(\d+)\s*(.*)$/)
  if (mm) m[mm[1].padStart(2, '0')] = mm[2].trim()
}
const keys = Object.keys(m).sort((a, b) => parseInt(a, 10) - parseInt(b, 10))

// 族模板标签：去重后 23 个改写族，由 manifest.csv 的 archetype 给出
const ARCHETYPE_LABELS = {
  sma: '双均线模版',
  sma_cross: '双均线金叉模版',
  ma_trend: '多均线趋势模版',
  ema: 'EMA交叉模版',
  macd: 'MACD模版',
  kdj: 'KDJ/Stoch模版',
  boll: '布林带模版',
  zscore: 'ZScore均值回归',
  rsrs: 'RSRS择时模版',
  dmi: 'DMI择时模版',
  gftd: 'GFTD九转模版',
  bias: '乖离率BIAS模版',
  kama_atr: 'KAMA+ATR模版',
  turtle: '海龟通道模版',
  momentum: '动量突破模版',
  ml: '机器学习预测模版',
  value: '价值回归模版',
  smart_money: '聪明钱量价模版',
  fund_pe: '基金PE估值模版',
  sector_rotate: '板块动量模版',
  smallcap: '小市值轮动模版',
  grid: '低吸网格模版',
  trix_rsi: 'TRIX+RSI模版',
  wizard: '向导多因子模版',
}

let o = `/** 与 量化策略代码(99份) 目录下文件名同步（共 ${keys.length} 项）。\n * 99 份聚宽模板已去重改写为 23 个 vn.py CtaTemplate 族策略，见\n * trader/examples/cta_backtesting/rewritten_strategies/family_*.py。 */\n`
o += `export const STRATEGY_ARCHETYPE_LABEL: Record<string, string> = {\n`
for (const [k, v] of Object.entries(ARCHETYPE_LABELS)) {
  o += `  ${JSON.stringify(k)}: ${JSON.stringify(v)},\n`
}
o += `}\n\n`
o += `export const STRATEGY_DISPLAY_NAMES: Record<string, string> = {\n`
for (const k of keys) {
  o += `  ${JSON.stringify(k)}: ${JSON.stringify(m[k])},\n`
}
o += `}\n\n`
o += `export function formatStrategyOptionLabel(\n`
o += `  strategyId: string,\n`
o += `  className?: string,\n`
o += `  locked?: boolean,\n`
o += `  archetype?: string,\n`
o += `): string {\n`
o += `  const id = (strategyId || '').trim()\n`
o += `  const key = id.length <= 2 ? id.padStart(2, '0') : id\n`
o += `  const title = STRATEGY_DISPLAY_NAMES[key] ?? STRATEGY_DISPLAY_NAMES[id]\n`
o += `  const lockSuffix = locked ? '（会员）' : ''\n`
o += `  const archLabel = archetype ? STRATEGY_ARCHETYPE_LABEL[archetype] : undefined\n`
o += `  const archSuffix = archLabel ? \` · [\${archLabel}]\` : ''\n`
o += `  if (title) return \`\${id} · \${title}\${archSuffix}\${lockSuffix}\`\n`
o += `  if (className) return \`\${id} · \${className}\${archSuffix}\${lockSuffix}\`\n`
o += `  return \`\${id}\${archSuffix}\${lockSuffix}\`\n`
o += `}\n`

fs.mkdirSync(path.dirname(outPath), { recursive: true })
fs.writeFileSync(outPath, o, 'utf8')
console.log('wrote', outPath, 'entries=', keys.length)
