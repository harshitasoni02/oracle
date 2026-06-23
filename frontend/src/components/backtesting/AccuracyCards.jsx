import React from 'react'
import { TrendingUp, Percent, Activity, BarChart2, Hash, Award } from 'lucide-react'

// ── Skeleton card shown while loading ──────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="bg-surface border border-border rounded-xl p-4 animate-pulse">
      <div className="h-3 w-16 bg-border rounded mb-3" />
      <div className="h-7 w-24 bg-border rounded mb-2" />
      <div className="h-2 w-20 bg-border rounded" />
    </div>
  )
}

// ── Single stat card ────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, sub, accentColor, isBest }) {
  return (
    <div
      className="bg-surface border rounded-xl p-4 relative overflow-hidden transition-all hover:border-opacity-80"
      style={{ borderColor: isBest ? accentColor + '60' : '#30363D' }}
    >
      {isBest && (
        <div
          className="absolute top-0 right-0 text-[10px] font-bold px-2 py-0.5 rounded-bl-lg"
          style={{ backgroundColor: accentColor + '25', color: accentColor }}
        >
          BEST
        </div>
      )}
      <div className="flex items-center gap-2 mb-2">
        <Icon size={13} style={{ color: accentColor }} />
        <span className="text-xs text-muted">{label}</span>
      </div>
      <p
        className="text-xl font-bold mono leading-tight"
        style={{ color: accentColor }}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-muted mt-1">{sub}</p>}
    </div>
  )
}

// ── Main component ──────────────────────────────────────────────────────────
// Props:
//   bestResult  – single BacktestResult object (the top-ranked strategy)
//   allResults  – array of all BacktestResult objects for current filters
//   isLoading   – boolean

export default function AccuracyCards({ bestResult, allResults, isLoading }) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[...Array(6)].map((_, i) => <SkeletonCard key={i} />)}
      </div>
    )
  }

  if (!bestResult) {
    return null
  }

  const totalTrades = allResults.reduce((s, r) => s + (r.total_trades || 0), 0)

  const cards = [
    {
      icon: Award,
      label: 'Best Strategy',
      value: bestResult.strategy.toUpperCase(),
      sub: `Horizon: ${bestResult.horizon}`,
      accentColor: '#F0A500',
      isBest: true,
    },
    {
      icon: Percent,
      label: 'Accuracy',
      value: `${bestResult.accuracy.toFixed(1)}%`,
      sub: 'Directional accuracy',
      accentColor: bestResult.accuracy >= 60 ? '#3FB950' : bestResult.accuracy >= 50 ? '#F0A500' : '#F85149',
    },
    {
      icon: TrendingUp,
      label: 'Win Rate',
      value: `${bestResult.win_rate.toFixed(1)}%`,
      sub: 'Profitable trades',
      accentColor: bestResult.win_rate >= 55 ? '#3FB950' : bestResult.win_rate >= 45 ? '#F0A500' : '#F85149',
    },
    {
      icon: BarChart2,
      label: 'Profit Factor',
      value: bestResult.profit_factor.toFixed(2),
      sub: 'Gross profit / loss',
      accentColor: bestResult.profit_factor >= 1.5 ? '#3FB950' : bestResult.profit_factor >= 1.0 ? '#F0A500' : '#F85149',
    },
    {
      icon: Hash,
      label: 'Total Trades',
      value: totalTrades.toLocaleString(),
      sub: `Across ${allResults.length} strategies`,
      accentColor: '#58A6FF',
    },
    {
      icon: Activity,
      label: 'Sharpe Ratio',
      value: bestResult.sharpe_ratio.toFixed(2),
      sub: 'Risk-adjusted return',
      accentColor: bestResult.sharpe_ratio >= 1 ? '#3FB950' : bestResult.sharpe_ratio >= 0 ? '#F0A500' : '#F85149',
    },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((card) => (
        <StatCard key={card.label} {...card} />
      ))}
    </div>
  )
}
