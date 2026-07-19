import React, { useState } from 'react'
import { ChevronUp, ChevronDown } from 'lucide-react'

// ── Colour helpers (mirrors SignalTable badge style) ────────────────────────

function pctColor(value, goodThreshold, warnThreshold) {
  if (value >= goodThreshold) return '#3FB950'
  if (value >= warnThreshold) return '#F0A500'
  return '#F85149'
}

function pfColor(pf) {
  if (pf >= 1.5) return '#3FB950'
  if (pf >= 1.0) return '#F0A500'
  return '#F85149'
}

function ValueBadge({ value, color }) {
  return (
    <span
      className="px-2 py-0.5 rounded text-xs font-medium mono"
      style={{ color, backgroundColor: color + '18' }}
    >
      {value}
    </span>
  )
}

const STRATEGY_DISPLAY = {
  rsi: 'RSI',
  macd: 'MACD',
  composite: 'Composite',
}

const COLUMNS = [
  { key: 'strategy',      label: 'Strategy',       sortable: false },
  { key: 'accuracy',      label: 'Accuracy',        sortable: true  },
  { key: 'win_rate',      label: 'Win Rate',        sortable: true  },
  { key: 'profit_factor', label: 'Profit Factor',   sortable: true  },
  { key: 'total_trades',  label: 'Trades',          sortable: true  },
  { key: 'sharpe_ratio',  label: 'Sharpe',          sortable: true  },
  { key: 'total_return',  label: 'Total Return',    sortable: true  },
]

function SortIcon({ active, dir }) {
  if (!active) return <ChevronUp size={11} className="text-muted/40" />
  return dir === 'desc'
    ? <ChevronDown size={11} className="text-gold" />
    : <ChevronUp size={11} className="text-gold" />
}

function SkeletonRow() {
  return (
    <tr className="border-t border-border">
      {COLUMNS.map((c) => (
        <td key={c.key} className="px-4 py-3">
          <div className="h-4 bg-border rounded animate-pulse w-16" />
        </td>
      ))}
    </tr>
  )
}

// ── Main component ──────────────────────────────────────────────────────────
// Props:
//   results   – BacktestResult[]
//   isLoading – boolean

export default function StrategyTable({ results, isLoading }) {
  const [sortKey, setSortKey] = useState('accuracy')
  const [sortDir, setSortDir] = useState('desc')

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sorted = [...(results || [])].sort((a, b) => {
    const av = a[sortKey] ?? 0
    const bv = b[sortKey] ?? 0
    return sortDir === 'desc' ? bv - av : av - bv
  })

  const bestAccuracy = sorted.length ? Math.max(...sorted.map(r => r.accuracy)) : 0

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-bg">
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide whitespace-nowrap select-none ${col.sortable ? 'cursor-pointer hover:text-white transition-colors' : ''}`}
                  onClick={() => col.sortable && handleSort(col.key)}
                >
                  <span className="flex items-center gap-1">
                    {col.label}
                    {col.sortable && <SortIcon active={sortKey === col.key} dir={sortDir} />}
                  </span>
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {isLoading ? (
              [...Array(4)].map((_, i) => <SkeletonRow key={i} />)
            ) : !sorted.length ? (
              <tr>
                <td colSpan={COLUMNS.length} className="px-4 py-10 text-center text-muted text-sm">
                  No backtest results yet.
                </td>
              </tr>
            ) : (
              sorted.map((row, idx) => {
                const isBest = row.accuracy === bestAccuracy
                return (
                  <tr
                    key={row.id ?? idx}
                    className={`border-t border-border transition-colors hover:bg-bg/60 ${isBest ? 'bg-gold/5' : ''}`}
                  >
                    {/* Strategy */}
                    <td className="px-4 py-3 font-medium text-white">
                      <span className="flex items-center gap-2">
                        {STRATEGY_DISPLAY[row.strategy] ?? row.strategy}
                        {isBest && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded font-bold bg-gold/20 text-gold">
                            BEST
                          </span>
                        )}
                      </span>
                    </td>

                    {/* Accuracy */}
                    <td className="px-4 py-3">
                      <ValueBadge
                        value={`${row.accuracy.toFixed(1)}%`}
                        color={pctColor(row.accuracy, 60, 50)}
                      />
                    </td>

                    {/* Win Rate */}
                    <td className="px-4 py-3">
                      <ValueBadge
                        value={`${row.win_rate.toFixed(1)}%`}
                        color={pctColor(row.win_rate, 55, 45)}
                      />
                    </td>

                    {/* Profit Factor */}
                    <td className="px-4 py-3">
                      <ValueBadge
                        value={row.profit_factor.toFixed(2)}
                        color={pfColor(row.profit_factor)}
                      />
                    </td>

                    {/* Total Trades */}
                    <td className="px-4 py-3 mono text-silver-light text-xs">
                      {row.total_trades}
                    </td>

                    {/* Sharpe */}
                    <td className="px-4 py-3 mono text-silver-light text-xs">
                      {row.sharpe_ratio.toFixed(2)}
                    </td>

                    {/* Total Return */}
                    <td className="px-4 py-3 mono text-xs">
                      <span style={{ color: row.total_return >= 0 ? '#3FB950' : '#F85149' }}>
                        {row.total_return >= 0 ? '+' : ''}{row.total_return.toFixed(2)}%
                      </span>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
