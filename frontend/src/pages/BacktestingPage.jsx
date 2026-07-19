import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { BarChart2, ArrowLeft, FlaskConical, AlertTriangle, Clock } from 'lucide-react'

import { api } from '../services/api.js'
import AccuracyCards from '../components/backtesting/AccuracyCards'
import StrategyTable from '../components/backtesting/StrategyTable'
import {
  AccuracyChart,
  WinRateChart,
  ProfitFactorChart,
  OverviewChart,
} from '../components/backtesting/BacktestCharts'

// ── Constants ──────────────────────────────────────────────────────────────

const METALS   = ['gold', 'silver']
const HORIZONS = ['1d', '1w']

const HORIZON_LABELS = { '1d': 'Next Day', '1w': 'Next Week' }
const METAL_EMOJI    = { gold: '🥇', silver: '🥈' }
const STRATEGY_DISPLAY = {
  rsi: 'RSI', macd: 'MACD', composite: 'Composite',
}

// ── Small reusable selector button group ───────────────────────────────────

function SelectorGroup({ label, value, options, labelMap, onChange }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-muted font-medium">{label}</span>
      <div className="flex gap-1">
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              value === opt
                ? 'bg-gold/20 text-gold border border-gold/40'
                : 'bg-bg text-muted border border-border hover:text-white hover:border-border/80'
            }`}
          >
            {labelMap ? labelMap[opt] : opt.toUpperCase()}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Strategy Ranking Card ──────────────────────────────────────────────────

function StrategyRanking({ results }) {
  if (!results?.length) return null

  const sorted = [...results].sort(
    (a, b) => b.accuracy - a.accuracy
  )

  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
        Strategy Ranking
        <span className="text-xs text-muted font-normal">by accuracy</span>
      </h3>
      <div className="space-y-2">
        {sorted.map((r, idx) => {
          const pct = r.accuracy
          const barColor = pct >= 60 ? '#3FB950' : pct >= 50 ? '#F0A500' : '#F85149'
          return (
            <div key={r.id ?? idx}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span
                    className="w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold"
                    style={{
                      backgroundColor: idx === 0 ? '#F0A50020' : '#30363D',
                      color: idx === 0 ? '#F0A500' : '#8B949E',
                    }}
                  >
                    {idx + 1}
                  </span>
                  <span className="text-sm text-white font-medium">
                    {STRATEGY_DISPLAY[r.strategy] ?? r.strategy}
                  </span>
                </div>
                <span className="mono text-xs" style={{ color: barColor }}>
                  {r.accuracy.toFixed(1)}%
                </span>
              </div>
              <div className="h-1.5 bg-bg rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${pct}%`, backgroundColor: barColor }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Loading skeleton for summary cards row ─────────────────────────────────

function SummaryCardsSkeleton() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="bg-surface border border-border rounded-xl p-4 animate-pulse">
          <div className="h-3 w-16 bg-border rounded mb-3" />
          <div className="h-7 w-20 bg-border rounded mb-2" />
          <div className="h-2 w-14 bg-border rounded" />
        </div>
      ))}
    </div>
  )
}

// ── Error banner (same style as OraclePage) ────────────────────────────────

function ErrorBanner({ message, onRetry }) {
  return (
    <div className="flex items-center gap-2 bg-bear/10 border border-bear/30 text-bear rounded-lg px-4 py-2 text-sm">
      <AlertTriangle size={16} />
      <span>{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="ml-2 underline text-bear hover:text-bear/80">
          Retry
        </button>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Main BacktestingPage
// ═══════════════════════════════════════════════════════════════════════════

export default function BacktestingPage() {
  const [metal, setMetal]     = useState('gold')
  const [horizon, setHorizon] = useState('1w')
  const navigate              = useNavigate()

  // Map backtest horizon → prediction timeframe for verification filtering
  const HORIZON_TO_TIMEFRAME = { '1d': '1d', '1w': '1w' }
  const predTimeframe = HORIZON_TO_TIMEFRAME[horizon] || '1d'

  // ── API calls ────────────────────────────────────────────────────────────

  const resultsQuery = useQuery({
    queryKey: ['backtest-results', metal, horizon],
    queryFn: () => api.getBacktestResults({ metal, horizon }),
    staleTime: 5 * 60 * 1000,
    retry: 2,
  })

  const summaryQuery = useQuery({
    queryKey: ['backtest-summary', metal, horizon],
    queryFn: () => api.getBacktestSummary(metal, horizon),
    staleTime: 5 * 60 * 1000,
    retry: 2,
  })
  const verificationQuery = useQuery({
  queryKey: ['verification-stats', metal, predTimeframe],
  queryFn: () => api.getVerificationStats(metal, predTimeframe),
  staleTime: 5 * 60 * 1000,
  retry: 2,
})
const verificationHistoryQuery = useQuery({
  queryKey: ['verification-history', metal, predTimeframe],
  queryFn: () => api.getVerificationHistory(metal, predTimeframe),
  staleTime: 5 * 60 * 1000,
  retry: 2,
})

  // ── Derived data ─────────────────────────────────────────────────────────

  const results  = resultsQuery.data  || []
  const summary  = summaryQuery.data  || []
  const verification = verificationQuery.data
  const verificationHistory =
  verificationHistoryQuery.data?.results || []



  // Flatten summary → all strategy rows for the current metal+horizon
  const allStrategies = summary.flatMap(s => s.strategies || [])

  // Pick best result by accuracy
  const bestResult = allStrategies.length
    ? allStrategies.reduce((best, r) => r.accuracy > best.accuracy ? r : best, allStrategies[0])
    : results.length
    ? results.reduce((best, r) => r.accuracy > best.accuracy ? r : best, results[0])
    : null

  const tableData  = allStrategies.length ? allStrategies : results
  const isLoading  = resultsQuery.isLoading || summaryQuery.isLoading
  const hasError   = resultsQuery.isError   || summaryQuery.isError
  const isEmpty    = !isLoading && !hasError && !tableData.length

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-bg text-white">

      {/* ── Header (same structure as OraclePage) ─────────────────────── */}
      <header className="border-b border-border bg-surface/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-[1600px] mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/')}
              className="flex items-center gap-1.5 text-muted hover:text-white transition-colors mr-1"
              aria-label="Back to dashboard"
            >
              <ArrowLeft size={16} />
            </button>
            <BarChart2 size={20} className="text-gold" />
            <span className="font-bold text-white text-lg">Shizuha Oracle</span>
            <span className="text-xs text-muted bg-border px-2 py-0.5 rounded flex items-center gap-1.5">
              <FlaskConical size={11} />
              Backtesting
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted">
            <span className="hidden sm:block">Historical signal validation</span>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-4 py-5 space-y-5">

        {/* ── Controls row ────────────────────────────────────────────── */}
        <div className="bg-surface border border-border rounded-xl px-5 py-4 flex flex-wrap items-end gap-5">
          <SelectorGroup
            label="Metal"
            value={metal}
            options={METALS}
            labelMap={{ gold: `${METAL_EMOJI.gold} Gold`, silver: `${METAL_EMOJI.silver} Silver` }}
            onChange={(m) => setMetal(m)}
          />
          <SelectorGroup
            label="Prediction Horizon"
            value={horizon}
            options={HORIZONS}
            labelMap={HORIZON_LABELS}
            onChange={setHorizon}
          />
          <div className="ml-auto text-xs text-muted">
            Evaluating RSI · MACD · Composite strategies
          </div>
        </div>

        {/* ── Error banner ────────────────────────────────────────────── */}
        {hasError && (
          <ErrorBanner
            message="Could not load backtest data. Run POST /api/backtesting/run/ to generate results."
            onRetry={() => {
              resultsQuery.refetch()
              summaryQuery.refetch()
            }}
          />
        )}

        {/* ── Empty state ──────────────────────────────────────────────── */}
        {isEmpty && (
          <div className="bg-surface border border-border rounded-xl p-10 text-center space-y-2">
            <FlaskConical size={32} className="text-muted mx-auto mb-3" />
            <p className="text-white font-semibold">No backtest results yet</p>
            <p className="text-muted text-sm max-w-md mx-auto">
              Trigger a run via the API or Celery beat to generate results for this metal and horizon combination.
            </p>
            <code className="block mt-3 text-xs text-muted bg-bg border border-border rounded px-4 py-2 font-mono max-w-sm mx-auto text-left">
              POST /api/backtesting/run/<br />
              {'{'} "metal": "{metal}", "timeframe": "1d", "horizon": "{horizon}" {'}'}
            </code>
          </div>
        )}

        {/* ── Summary cards ────────────────────────────────────────────── */}
        {(isLoading || bestResult) && (
          isLoading
            ? <SummaryCardsSkeleton />
            : (
              <AccuracyCards
                bestResult={bestResult}
                allResults={tableData}
                isLoading={false}
              />
            )
        )}

        {/* ── Main grid: table + ranking ────────────────────────────────── */}
        {(isLoading || tableData.length > 0) && (
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_260px] gap-5">

            {/* Strategy table */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-white">
                  Strategy Performance
                </h2>
                <span className="text-xs text-muted">
                  {metal === 'gold' ? '🥇 Gold' : '🥈 Silver'} · {HORIZON_LABELS[horizon]}
                </span>
              </div>
              <StrategyTable results={tableData} isLoading={isLoading} />
            </div>

            {/* Ranking sidebar */}
            <div className="space-y-4">
              <StrategyRanking results={tableData} />

              {/* India note — same as OraclePage sidebar */}
              <div className="bg-surface border border-border rounded-xl p-4 text-xs text-muted space-y-1.5">
                <p className="font-semibold text-white text-xs mb-2">About Backtesting</p>
                <p>Results are computed on historical COMEX/yfinance OHLCV data.</p>
                <p className="text-muted/70 leading-relaxed pt-1">
                  Past signal accuracy does not guarantee future performance.
                  Signals do not account for bid-ask spread, slippage, or MCX
                  trading costs. Not financial advice.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ── Charts grid ───────────────────────────────────────────────── */}
        {tableData.length > 0 && (
          <div className="space-y-5">
            {/* Overview (full width) */}
            <OverviewChart results={tableData} />

            {/* Three detail charts */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <AccuracyChart     results={tableData} />
              <WinRateChart      results={tableData} />
              <ProfitFactorChart results={tableData} />
            </div>
          </div>
        )}

        {/* ── Prediction Verification ──────────────────────────────────── */}

        <div className="bg-surface border border-border rounded-xl p-5">
  <div className="flex items-center gap-2 mb-4">
    <Clock size={14} className="text-muted" />
    <h3 className="text-sm font-semibold text-muted">
      Prediction Verification
    </h3>
  </div>

  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">

    <div className="bg-bg rounded-lg p-3 text-center">
      <p className="text-xs text-muted">MAE</p>
      <p className="text-xl font-bold">
        {verification?.mae?.toFixed(2) ?? '--'}
      </p>
    </div>
    
    

    <div className="bg-bg rounded-lg p-3 text-center">
      <p className="text-xs text-muted">RMSE</p>
      <p className="text-xl font-bold">
        {verification?.rmse?.toFixed(2) ?? '--'}
      </p>
    </div>

    <div className="bg-bg rounded-lg p-3 text-center">
      <p className="text-xs text-muted">MAPE</p>
      <p className="text-xl font-bold">
        {verification?.mape?.toFixed(2) ?? '--'}%
      </p>
    </div>

    <div className="bg-bg rounded-lg p-3 text-center">
      <p className="text-xs text-muted">Direction Accuracy</p>
      <p className="text-xl font-bold">
        {verification?.directional_accuracy?.toFixed(1) ?? '--'}%
      </p>
    </div>
  </div>
  <div className="mt-5">
    <h4 className="text-sm font-semibold text-muted mb-3">
      Verification History ({verificationHistory.length})
    </h4>

    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left py-2 whitespace-nowrap">Prediction Date</th>
            <th className="text-left py-2 whitespace-nowrap">Target Date</th>
            <th className="text-left py-2 whitespace-nowrap">Previous Price</th>
            <th className="text-left py-2 whitespace-nowrap">Predicted Price</th>
            <th className="text-left py-2 whitespace-nowrap">Actual Price</th>
            <th className="text-left py-2 whitespace-nowrap">Error %</th>
            <th className="text-left py-2 whitespace-nowrap">Direction</th>
          </tr>
        </thead>

        <tbody>
          {verificationHistory.map((item, index) => {
            const predDate = item.prediction_date ? new Date(item.prediction_date) : null
            const targetDate = item.target_date ? new Date(item.target_date) : null
            const dirLabel = item.actual_direction === 'up' ? 'UP'
                             : item.actual_direction === 'down' ? 'DOWN'
                             : 'SIDEWAYS'
            const dirColor = item.actual_direction === 'up' ? 'text-green-400'
                            : item.actual_direction === 'down' ? 'text-red-400'
                            : 'text-muted'

            // Format as "24 Jun 2026 01:45 AM"
            function formatDateTime(d) {
              if (!d) return '--'
              const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
              const day = d.getDate()
              const month = months[d.getMonth()]
              const year = d.getFullYear()
              let hours = d.getHours()
              const minutes = String(d.getMinutes()).padStart(2, '0')
              const ampm = hours >= 12 ? 'PM' : 'AM'
              hours = hours % 12 || 12
              return `${day} ${month} ${year} ${hours}:${minutes} ${ampm}`
            }

            return (
              <tr key={index} className="border-b border-border/30">
                <td className="py-2 text-xs whitespace-nowrap">
                  {formatDateTime(predDate)}
                </td>
                <td className="py-2 text-xs whitespace-nowrap">
                  {targetDate ? targetDate.toLocaleDateString() : '--'}
                </td>
                <td className="py-2 mono">${item.previous_price?.toFixed(2)}</td>
                <td className="py-2 mono">${item.predicted_price?.toFixed(2)}</td>
                <td className="py-2 mono">${item.actual_price?.toFixed(2)}</td>
                <td className="py-2 mono">
                  <span style={{ color: item.percentage_error <= 2 ? '#3FB950' : item.percentage_error <= 5 ? '#F0A500' : '#F85149' }}>
                    {item.percentage_error?.toFixed(2)}%
                  </span>
                </td>
                <td className={`py-2 font-semibold ${dirColor}`}>
                  {dirLabel}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  </div>
</div>

      </main>
    </div>
  )
}
