import React from 'react'
import { clsx } from 'clsx'

const METALS = [
  { key: 'gold',   label: 'Gold',   emoji: '🥇', color: '#F0A500' },
  { key: 'silver', label: 'Silver', emoji: '🥈', color: '#A0ADB7' },
]

const TIMEFRAMES = [
  { key: '1m',  label: '1m' },
  { key: '5m',  label: '5m' },
  { key: '15m', label: '15m' },
  { key: '1h',  label: '1h' },
  { key: '1d',  label: '1D' },
  { key: '1w',  label: '1W' },
]

export default function MetalTimeframeBar({ metal, timeframe, onMetalChange, onTimeframeChange }) {
  const currentMetal = METALS.find(m => m.key === metal)

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
      {/* Metal selector */}
      <div className="flex gap-2">
        {METALS.map(m => (
          <button
            key={m.key}
            onClick={() => onMetalChange(m.key)}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm transition-all',
              metal === m.key
                ? 'text-white shadow-md'
                : 'bg-surface border border-border text-muted hover:text-white'
            )}
            style={metal === m.key ? { backgroundColor: m.color + '25', border: `1px solid ${m.color}60`, color: m.color } : {}}
          >
            <span className="text-base">{m.emoji}</span>
            {m.label}
          </button>
        ))}
      </div>

      {/* Timeframe selector */}
      <div className="flex bg-surface border border-border rounded-lg p-0.5 gap-0.5">
        {TIMEFRAMES.map(tf => (
          <button
            key={tf.key}
            onClick={() => onTimeframeChange(tf.key)}
            className={clsx(
              'px-3 py-1.5 rounded text-xs font-medium transition-all',
              timeframe === tf.key
                ? 'text-white'
                : 'text-muted hover:text-white'
            )}
            style={timeframe === tf.key ? {
              backgroundColor: currentMetal?.color + '25',
              color: currentMetal?.color,
            } : {}}
          >
            {tf.label}
          </button>
        ))}
      </div>
    </div>
  )
}
