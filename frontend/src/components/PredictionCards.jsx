import React, { useState } from 'react'
import { TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp } from 'lucide-react'

function fmt(n, dec = 2) {
  if (n == null) return '—'
  return new Intl.NumberFormat('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(n)
}

const DIRECTION_CONFIG = {
  up: { icon: TrendingUp, color: '#3FB950', bg: '#3FB95015', label: 'Bullish' },
  down: { icon: TrendingDown, color: '#F85149', bg: '#F8514915', label: 'Bearish' },
  sideways: { icon: Minus, color: '#8B949E', bg: '#8B949E15', label: 'Sideways' },
}

const SIGNAL_COLOR = {
  'Strong Buy': '#3FB950',
  'Buy': '#85E089',
  'Neutral': '#8B949E',
  'Sell': '#FF7B72',
  'Strong Sell': '#F85149',
}

const TIMEFRAME_ORDER = ['1d', '1w', '2w', '1m', '3m', '6m', '1y']
const SHORT_TERM = new Set(['1d', '1w', '2w'])

function ConfidenceBar({ value }) {
  const color = value >= 65 ? '#3FB950' : value >= 50 ? '#F0A500' : '#F85149'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${value}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs mono" style={{ color }}>{value}%</span>
    </div>
  )
}

function PredictionCard({ prediction, metal }) {
  const [expanded, setExpanded] = useState(false)
  const dir = DIRECTION_CONFIG[prediction.direction] || DIRECTION_CONFIG.sideways
  const Icon = dir.icon
  const sigColor = SIGNAL_COLOR[prediction.signal_label] || '#8B949E'
  const isShort = SHORT_TERM.has(prediction.timeframe)
  const changePct = prediction.change_pct

  return (
    <div className="bg-bg border border-border rounded-xl p-4 hover:border-border/80 transition-all">
      {/* Header row */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-xs text-muted">{isShort ? 'Short-term' : 'Long-term'}</p>
          <p className="font-semibold text-white">{prediction.timeframe_label}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs px-2 py-0.5 rounded font-medium"
            style={{ color: sigColor, backgroundColor: sigColor + '20' }}>
            {prediction.signal_label}
          </span>
          <div className="w-8 h-8 rounded-full flex items-center justify-center"
            style={{ backgroundColor: dir.bg }}>
            <Icon size={16} style={{ color: dir.color }} />
          </div>
        </div>
      </div>

      {/* Predicted prices */}
      <div className="mb-3">
        <div className="flex items-end gap-2">
          <span className="text-xl font-bold mono text-white">
            ${fmt(prediction.predicted_usd)}
          </span>
          <span className={`text-sm font-medium pb-0.5 ${changePct >= 0 ? 'text-bull' : 'text-bear'}`}>
            {changePct >= 0 ? '+' : ''}{fmt(changePct)}%
          </span>
        </div>
        <p className="text-xs text-muted mono mt-0.5">
          ₹{fmt(prediction.predicted_per_gram_inr || (prediction.predicted_inr / 31.1035), 0)}/g
          {metal === 'gold' && <span> · ₹{fmt((prediction.predicted_inr / 31.1035) * 10, 0)}/10g</span>}
          {metal === 'silver' && <span> · ₹{fmt(prediction.predicted_inr / 31.1035 * 1000, 0)}/kg</span>}
        </p>
      </div>

      {/* Range bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-muted mb-1">
          <span>Low: ${fmt(prediction.predicted_low_usd)}</span>
          <span>High: ${fmt(prediction.predicted_high_usd)}</span>
        </div>
        {(() => {
          const low = prediction.predicted_low_usd
          const high = prediction.predicted_high_usd
          const pred = prediction.predicted_usd
          const total = high - low || 1
          const pctPos = ((pred - low) / total) * 100
          return (
            <div className="relative h-2 bg-border rounded-full overflow-hidden">
              <div className="absolute inset-0 rounded-full"
                style={{ background: 'linear-gradient(to right, #F85149, #3FB950)' }} />
              <div className="absolute top-0 bottom-0 w-1.5 bg-white rounded-full shadow"
                style={{ left: `calc(${pctPos}% - 3px)` }} />
            </div>
          )
        })()}
      </div>

      {/* Confidence */}
      <div className="mb-2">
        <div className="flex justify-between text-xs text-muted mb-1">
          <span>Confidence</span>
          <span className="mono">{prediction.confidence}%</span>
        </div>
        <ConfidenceBar value={prediction.confidence} />
      </div>

      {/* Method badge */}
      <p className="text-xs text-muted mt-2">
        {isShort ? '⚡ Technical signals + ATR' : '📈 Linear regression + seasonality'}
      </p>

      {/* Rationale expandable */}
      {prediction.rationale?.length > 0 && (
        <div className="mt-2 border-t border-border pt-2">
          <button
            onClick={() => setExpanded(v => !v)}
            className="flex items-center gap-1 text-xs text-muted hover:text-white transition-colors"
          >
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {expanded ? 'Hide' : 'Show'} rationale
          </button>
          {expanded && (
            <ul className="mt-2 space-y-1">
              {prediction.rationale.map((r, i) => (
                <li key={i} className="text-xs text-muted flex items-start gap-1.5">
                  <span className="text-muted mt-0.5">•</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export default function PredictionCards({ predictions, metal }) {
  if (!predictions?.length) {
    return (
      <div className="bg-surface border border-border rounded-xl p-4 text-center">
        <p className="text-muted text-sm">No predictions yet. Trigger a refresh to generate.</p>
      </div>
    )
  }

  const sorted = [...predictions].sort(
    (a, b) => TIMEFRAME_ORDER.indexOf(a.timeframe) - TIMEFRAME_ORDER.indexOf(b.timeframe)
  )

  const shortTerm = sorted.filter(p => SHORT_TERM.has(p.timeframe))
  const longTerm = sorted.filter(p => !SHORT_TERM.has(p.timeframe))

  return (
    <div>
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          ⚡ Short-Term Predictions
          <span className="text-xs text-muted font-normal">(signal-based)</span>
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {shortTerm.map(p => (
            <PredictionCard key={p.timeframe} prediction={p} metal={metal} />
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          📈 Long-Term Predictions
          <span className="text-xs text-muted font-normal">(regression + India seasonality)</span>
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {longTerm.map(p => (
            <PredictionCard key={p.timeframe} prediction={p} metal={metal} />
          ))}
        </div>
      </div>

      <p className="text-xs text-muted mt-4 p-3 bg-surface border border-border rounded-lg">
        ⚠️ These predictions are generated using technical analysis indicators and statistical regression.
        They are for informational purposes only and do not constitute financial advice.
        Past performance does not guarantee future results. Gold/silver prices are influenced by geopolitical events,
        central bank policy, currency movements, and many other factors that cannot be modeled purely technically.
      </p>
    </div>
  )
}
