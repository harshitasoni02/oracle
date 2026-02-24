import React from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

const SIGNAL_STYLES = {
  'Strong Buy':  { color: '#3FB950', bg: '#3FB95018', dot: '🟢' },
  'Buy':         { color: '#85E089', bg: '#85E08918', dot: '🟢' },
  'Weak Buy':    { color: '#85E089', bg: '#85E08910', dot: '🟡' },
  'Neutral':     { color: '#8B949E', bg: '#8B949E18', dot: '⚪' },
  'Weak Sell':   { color: '#FF7B72', bg: '#FF7B7210', dot: '🟡' },
  'Sell':        { color: '#FF7B72', bg: '#FF7B7218', dot: '🔴' },
  'Strong Sell': { color: '#F85149', bg: '#F8514918', dot: '🔴' },
  'N/A':         { color: '#6E7681', bg: 'transparent', dot: '—' },
}

function SignalBadge({ label }) {
  const style = SIGNAL_STYLES[label] || SIGNAL_STYLES['N/A']
  return (
    <span
      className="px-2 py-0.5 rounded text-xs font-medium"
      style={{ color: style.color, backgroundColor: style.bg }}
    >
      {label}
    </span>
  )
}

function CompositeGauge({ score, label }) {
  const pct = ((score + 1) / 2) * 100  // map -1..+1 → 0..100
  const style = SIGNAL_STYLES[label] || SIGNAL_STYLES['Neutral']

  return (
    <div className="bg-bg rounded-xl p-4 mb-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-white">Composite Signal</span>
        <SignalBadge label={label} />
      </div>
      {/* Gauge bar */}
      <div className="relative h-3 bg-border rounded-full overflow-hidden mb-1">
        {/* Gradient background */}
        <div className="absolute inset-0 rounded-full"
          style={{ background: 'linear-gradient(to right, #F85149, #8B949E 50%, #3FB950)' }} />
        {/* Needle */}
        <div className="absolute top-0 bottom-0 w-1 bg-white rounded-full shadow-md"
          style={{ left: `calc(${pct}% - 2px)` }} />
      </div>
      <div className="flex justify-between text-xs text-muted">
        <span>Strong Sell</span>
        <span className="mono font-medium" style={{ color: style.color }}>
          {score >= 0 ? '+' : ''}{score.toFixed(2)}
        </span>
        <span>Strong Buy</span>
      </div>
    </div>
  )
}

const INDICATOR_ROWS = [
  { key: 'rsi',          label: 'RSI (14)',         format: (v) => v?.toFixed(1) },
  { key: 'macd',         label: 'MACD',             format: (v) => v?.toFixed(2) },
  { key: 'stochastic',   label: 'Stochastic %K',    format: (v, ind) => ind?.stoch_k?.toFixed(1) },
  { key: 'cci',          label: 'CCI (20)',          format: (v, ind) => ind?.cci?.toFixed(1) },
  { key: 'williams_r',   label: 'Williams %R',       format: (v, ind) => ind?.williams_r?.toFixed(1) },
  { key: 'bollinger',    label: 'Bollinger Bands',   format: (v, ind) => {
    if (!ind?.bb_upper || !ind?.bb_lower || !ind?.current_price) return '—'
    const pct = ((ind.current_price - ind.bb_lower) / (ind.bb_upper - ind.bb_lower) * 100)
    return pct.toFixed(0) + '%'
  }},
  { key: 'sma20',        label: 'SMA (20)',          format: (v, ind) => ind?.sma20 ? '$' + ind.sma20.toFixed(0) : '—' },
  { key: 'sma50',        label: 'SMA (50)',          format: (v, ind) => ind?.sma50 ? '$' + ind.sma50.toFixed(0) : '—' },
  { key: 'sma200',       label: 'SMA (200)',         format: (v, ind) => ind?.sma200 ? '$' + ind.sma200.toFixed(0) : '—' },
  { key: 'sma_alignment', label: 'SMA Alignment',   format: () => '—' },
  { key: 'news_sentiment', label: 'News Sentiment',  format: (v, ind) => {
    const sig = ind?.individual_signals?.news_sentiment
    if (!sig) return '—'
    return sig.score >= 0 ? `+${sig.score.toFixed(2)}` : sig.score.toFixed(2)
  }},
]

export default function SignalTable({ indicators }) {
  if (!indicators) {
    return (
      <div className="bg-surface border border-border rounded-xl p-4">
        <p className="text-muted text-sm text-center">No indicator data yet.</p>
      </div>
    )
  }

  const signals = indicators.individual_signals || {}
  const score = indicators.signal_score || 0
  const label = indicators.signal_label || 'Neutral'

  const buyCount = Object.values(signals).filter(s => s.score > 0.1).length
  const sellCount = Object.values(signals).filter(s => s.score < -0.1).length
  const neutralCount = Object.values(signals).length - buyCount - sellCount

  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
        Technical Analysis
        <span className="text-xs text-muted font-normal">(Daily)</span>
      </h3>

      <CompositeGauge score={score} label={label} />

      {/* Summary counts */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className="text-center bg-bg rounded-lg py-2">
          <p className="text-lg font-bold text-bull">{buyCount}</p>
          <p className="text-xs text-muted">Buy</p>
        </div>
        <div className="text-center bg-bg rounded-lg py-2">
          <p className="text-lg font-bold text-neutral">{neutralCount}</p>
          <p className="text-xs text-muted">Neutral</p>
        </div>
        <div className="text-center bg-bg rounded-lg py-2">
          <p className="text-lg font-bold text-bear">{sellCount}</p>
          <p className="text-xs text-muted">Sell</p>
        </div>
      </div>

      {/* Indicator table */}
      <div className="space-y-1">
        {INDICATOR_ROWS.map(({ key, label: rowLabel, format }) => {
          const sig = signals[key]
          const rawValue = key === 'rsi' ? indicators.rsi : null
          const displayVal = format(rawValue, indicators)
          return (
            <div key={key} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-bg/50 transition-colors">
              <span className="text-xs text-muted">{rowLabel}</span>
              <div className="flex items-center gap-3">
                {displayVal && displayVal !== '—' && (
                  <span className="text-xs mono text-silver-light">{displayVal}</span>
                )}
                {sig ? (
                  <SignalBadge label={sig.label} />
                ) : (
                  <span className="text-xs text-muted">—</span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* ATR */}
      {indicators.atr && (
        <div className="mt-3 pt-3 border-t border-border">
          <div className="flex justify-between text-xs">
            <span className="text-muted">ATR (14) — Volatility</span>
            <span className="mono text-white">${indicators.atr.toFixed(2)}</span>
          </div>
        </div>
      )}

      {/* DJI Correlation */}
      {indicators.dji_price && (
        <div className="mt-3 pt-3 border-t border-border">
          <p className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">
            Dow Jones Correlation
          </p>
          <div className="space-y-1">
            <div className="flex items-center justify-between py-1 px-2 rounded hover:bg-bg/50">
              <span className="text-xs text-muted">DJI Level</span>
              <span className="text-xs mono text-white">
                {indicators.dji_price?.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                {indicators.dji_change_pct != null && (
                  <span className={`ml-1.5 ${indicators.dji_change_pct >= 0 ? 'text-bull' : 'text-bear'}`}>
                    {indicators.dji_change_pct >= 0 ? '+' : ''}{indicators.dji_change_pct.toFixed(2)}%
                  </span>
                )}
              </span>
            </div>
            {indicators.dji_rsi != null && (
              <div className="flex items-center justify-between py-1 px-2 rounded hover:bg-bg/50">
                <span className="text-xs text-muted">DJI RSI (14)</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs mono text-white">{indicators.dji_rsi.toFixed(1)}</span>
                  {signals.dji_rsi && <SignalBadge label={signals.dji_rsi.label} />}
                </div>
              </div>
            )}
            {signals.dji_trend && (
              <div className="flex items-center justify-between py-1 px-2 rounded hover:bg-bg/50">
                <span className="text-xs text-muted">DJI Trend</span>
                <SignalBadge label={signals.dji_trend.label} />
              </div>
            )}
            {signals.dji_change && (
              <div className="flex items-center justify-between py-1 px-2 rounded hover:bg-bg/50">
                <span className="text-xs text-muted">DJI Day Move</span>
                <SignalBadge label={signals.dji_change.label} />
              </div>
            )}
          </div>
          <p className="text-xs text-muted mt-2 opacity-60">
            DJI rise = risk-on = bearish gold · DJI fall = safe-haven = bullish gold
          </p>
        </div>
      )}
    </div>
  )
}
