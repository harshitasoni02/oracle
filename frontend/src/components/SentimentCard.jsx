import React from 'react'
import { TrendingUp, TrendingDown, Minus, ExternalLink } from 'lucide-react'

// ---------------------------------------------------------------------------
// Signal styles — match labels from sentiment.py
// ---------------------------------------------------------------------------
const SIGNAL_STYLES = {
  'Strong Bullish': { color: '#3FB950', bg: '#3FB95018' },
  'Bullish':        { color: '#85E089', bg: '#85E08918' },
  'Neutral':        { color: '#8B949E', bg: '#8B949E18' },
  'Bearish':        { color: '#FF7B72', bg: '#FF7B7218' },
  'Strong Bearish': { color: '#F85149', bg: '#F8514918' },
  'No data yet':    { color: '#6E7681', bg: 'transparent' },
}

// Category chip colours
const CAT_STYLES = {
  FED:          { color: '#58A6FF', bg: '#58A6FF1A' },
  RBI:          { color: '#BC8CFF', bg: '#BC8CFF1A' },
  GEOPOLITICAL: { color: '#F0A500', bg: '#F0A5001A' },
  INDIA:        { color: '#FFD700', bg: '#FFD7001A' },
  ETF:          { color: '#79C0FF', bg: '#79C0FF1A' },
  INFLATION:    { color: '#FF9E64', bg: '#FF9E641A' },
  GENERAL:      { color: '#8B949E', bg: '#8B949E1A' },
}

const LABEL_STYLES = {
  Bullish:  { color: '#3FB950', bg: '#3FB95018' },
  Neutral:  { color: '#8B949E', bg: '#8B949E18' },
  Bearish:  { color: '#F85149', bg: '#F8514918' },
}

function SignalBadge({ label }) {
  const style = SIGNAL_STYLES[label] || SIGNAL_STYLES['Neutral']
  return (
    <span
      className="px-2 py-0.5 rounded text-xs font-medium"
      style={{ color: style.color, backgroundColor: style.bg }}
    >
      {label}
    </span>
  )
}

function CategoryChip({ cat }) {
  const style = CAT_STYLES[cat] || CAT_STYLES.GENERAL
  const short = { GEOPOLITICAL: 'GEO', INFLATION: 'INFL' }
  return (
    <span
      className="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide"
      style={{ color: style.color, backgroundColor: style.bg }}
    >
      {short[cat] || cat}
    </span>
  )
}

function SentimentChip({ value, label }) {
  if (value == null) {
    return (
      <div className="text-center">
        <p className="text-xs text-muted">—</p>
        <p className="text-[10px] text-muted/60 mt-0.5">{label}</p>
      </div>
    )
  }
  const color = value > 0.05 ? '#3FB950' : value < -0.05 ? '#F85149' : '#8B949E'
  return (
    <div className="text-center">
      <p className="text-sm font-bold mono" style={{ color }}>
        {value >= 0 ? '+' : ''}{value.toFixed(2)}
      </p>
      <p className="text-[10px] text-muted/60 mt-0.5">{label}</p>
    </div>
  )
}

function SentimentGauge({ score, label }) {
  const pct = ((score + 1) / 2) * 100
  const style = SIGNAL_STYLES[label] || SIGNAL_STYLES['Neutral']
  return (
    <div className="bg-bg rounded-xl p-4 mb-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-white">News Sentiment Signal</span>
        <SignalBadge label={label} />
      </div>
      <div className="relative h-3 bg-border rounded-full overflow-hidden mb-1">
        <div
          className="absolute inset-0 rounded-full"
          style={{ background: 'linear-gradient(to right, #F85149, #8B949E 50%, #3FB950)' }}
        />
        <div
          className="absolute top-0 bottom-0 w-1 bg-white rounded-full shadow-md"
          style={{ left: `calc(${pct}% - 2px)` }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted">
        <span>Strong Bearish</span>
        <span className="mono font-medium" style={{ color: style.color }}>
          {score >= 0 ? '+' : ''}{score.toFixed(2)}
        </span>
        <span>Strong Bullish</span>
      </div>
    </div>
  )
}

function MomentumArrow({ momentum }) {
  if (momentum == null) return null
  const isUp = momentum > 0.05
  const isDown = momentum < -0.05
  const color = isUp ? '#3FB950' : isDown ? '#F85149' : '#8B949E'
  const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus
  return (
    <div className="flex items-center gap-1.5 text-xs" style={{ color }}>
      <Icon size={14} />
      <span className="mono">{momentum >= 0 ? '+' : ''}{momentum.toFixed(2)}</span>
      <span className="text-muted">momentum</span>
    </div>
  )
}

function timeAgo(isoString) {
  if (!isoString) return ''
  const diff = (Date.now() - new Date(isoString).getTime()) / 1000
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function SentimentCard({ sentiment }) {
  if (!sentiment) {
    return (
      <div className="bg-surface border border-border rounded-xl p-4">
        <h3 className="text-sm font-semibold text-white mb-3">Market Sentiment</h3>
        <p className="text-muted text-sm text-center py-4">Loading news sentiment…</p>
      </div>
    )
  }

  const {
    signal_score = 0,
    signal_label = 'No data yet',
    sentiment_24h,
    sentiment_7d,
    sentiment_30d,
    sentiment_momentum,
    count_24h = 0,
    count_7d = 0,
    category_breakdown = {},
    top_articles = [],
  } = sentiment

  const articleCount = count_7d || count_24h
  const hasData = signal_label !== 'No data yet'

  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-white">Market Sentiment</h3>
        <div className="flex items-center gap-2">
          {articleCount > 0 && (
            <span className="text-[10px] text-muted bg-border px-2 py-0.5 rounded-full">
              {articleCount} articles
            </span>
          )}
        </div>
      </div>

      {!hasData ? (
        <p className="text-muted text-sm text-center py-4">
          No sentiment data yet. Trigger a refresh to fetch news.
        </p>
      ) : (
        <>
          {/* Gauge */}
          <SentimentGauge score={signal_score} label={signal_label} />

          {/* 3-window row */}
          <div className="grid grid-cols-3 gap-2 mb-4 bg-bg rounded-lg p-3">
            <SentimentChip value={sentiment_24h} label="24h" />
            <SentimentChip value={sentiment_7d} label="7d" />
            <SentimentChip value={sentiment_30d} label="30d" />
          </div>

          {/* Momentum */}
          {sentiment_momentum != null && (
            <div className="mb-4 flex items-center justify-between">
              <span className="text-xs text-muted">Momentum (7d vs 30d)</span>
              <MomentumArrow momentum={sentiment_momentum} />
            </div>
          )}

          {/* Category breakdown */}
          {Object.keys(category_breakdown).length > 0 && (
            <div className="mb-4">
              <p className="text-[10px] font-semibold text-muted uppercase tracking-wide mb-2">
                By Category (7d avg)
              </p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(category_breakdown).map(([cat, score]) => {
                  const catStyle = CAT_STYLES[cat] || CAT_STYLES.GENERAL
                  const scoreColor = score > 0.05 ? '#3FB950' : score < -0.05 ? '#F85149' : '#8B949E'
                  const short = { GEOPOLITICAL: 'GEO', INFLATION: 'INFL' }
                  return (
                    <div
                      key={cat}
                      className="flex items-center gap-1 px-2 py-1 rounded text-[10px]"
                      style={{ backgroundColor: catStyle.bg }}
                    >
                      <span style={{ color: catStyle.color }} className="font-semibold">
                        {short[cat] || cat}
                      </span>
                      <span className="mono" style={{ color: scoreColor }}>
                        {score >= 0 ? '+' : ''}{score.toFixed(2)}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Article feed */}
          {top_articles.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-muted uppercase tracking-wide mb-2">
                Recent News
              </p>
              <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
                {top_articles.map((art, i) => {
                  const lblStyle = LABEL_STYLES[art.label] || LABEL_STYLES.Neutral
                  return (
                    <a
                      key={i}
                      href={art.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-start gap-2 p-2 rounded-lg hover:bg-bg/60 transition-colors group cursor-pointer"
                    >
                      <div className="flex flex-col gap-1 flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <CategoryChip cat={art.category} />
                          <span
                            className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                            style={{ color: lblStyle.color, backgroundColor: lblStyle.bg }}
                          >
                            {art.label}
                          </span>
                          <span className="text-[10px] text-muted ml-auto shrink-0">
                            {art.source} · {timeAgo(art.published_at)}
                          </span>
                        </div>
                        <p className="text-xs text-white/80 leading-snug line-clamp-2">
                          {art.title}
                        </p>
                      </div>
                      <ExternalLink
                        size={11}
                        className="text-muted shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                      />
                    </a>
                  )
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
