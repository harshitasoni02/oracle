import React from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  Legend,
} from 'recharts'

// ── Oracle theme colours (match index.css vars) ────────────────────────────
const THEME = {
  bg:      '#0D1117',
  surface: '#161B22',
  border:  '#30363D',
  muted:   '#8B949E',
  gold:    '#F0A500',
  silver:  '#A0ADB7',
  bull:    '#3FB950',
  bear:    '#F85149',
  blue:    '#58A6FF',
  purple:  '#BC8CFF',
}

const STRATEGY_DISPLAY = {
  rsi:       'RSI',
  macd:      'MACD',
  composite: 'Composite',
}

// ── Shared tooltip ─────────────────────────────────────────────────────────

function OracleTooltip({ active, payload, label, unit = '' }) {
  if (!active || !payload?.length) return null
  return (
    <div
      className="rounded-lg border px-3 py-2 text-xs shadow-xl"
      style={{ backgroundColor: THEME.surface, borderColor: THEME.border }}
    >
      <p className="font-semibold text-white mb-1">{label}</p>
      {payload.map((entry) => (
        <div key={entry.dataKey} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.fill || entry.color }} />
          <span className="text-muted">{entry.name}:</span>
          <span className="mono font-medium" style={{ color: entry.fill || entry.color }}>
            {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}{unit}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Shared empty state ─────────────────────────────────────────────────────

function EmptyChart({ title }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      <h3 className="text-sm font-semibold text-white mb-4">{title}</h3>
      <div className="h-48 flex items-center justify-center text-muted text-sm">
        No data yet — run a backtest first.
      </div>
    </div>
  )
}

// ── Shared chart wrapper ───────────────────────────────────────────────────

function ChartCard({ title, children }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      <h3 className="text-sm font-semibold text-white mb-4">{title}</h3>
      {children}
    </div>
  )
}

// ── 1. Accuracy Comparison ─────────────────────────────────────────────────
// Horizontal bar chart: one bar per strategy, coloured by value

export function AccuracyChart({ results }) {
  if (!results?.length) return <EmptyChart title="Accuracy by Strategy" />

  const data = results.map((r) => ({
    name: STRATEGY_DISPLAY[r.strategy] ?? r.strategy,
    accuracy: parseFloat(r.accuracy.toFixed(1)),
  }))

  return (
    <ChartCard title="Accuracy by Strategy">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, left: 8, bottom: 0 }}>
          <CartesianGrid horizontal={false} stroke={THEME.border} strokeDasharray="3 3" />
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{ fill: THEME.muted, fontSize: 11 }}
            tickFormatter={(v) => `${v}%`}
            axisLine={{ stroke: THEME.border }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fill: THEME.muted, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={80}
          />
          <Tooltip content={<OracleTooltip unit="%" />} cursor={{ fill: THEME.border + '40' }} />
          <ReferenceLine x={50} stroke={THEME.muted} strokeDasharray="4 3" />
          <Bar dataKey="accuracy" name="Accuracy" radius={[0, 4, 4, 0]} maxBarSize={28}>
            {data.map((entry) => (
              <Cell
                key={entry.name}
                fill={
                  entry.accuracy >= 60 ? THEME.bull :
                  entry.accuracy >= 50 ? THEME.gold :
                  THEME.bear
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

// ── 2. Win Rate Comparison ─────────────────────────────────────────────────

export function WinRateChart({ results }) {
  if (!results?.length) return <EmptyChart title="Win Rate by Strategy" />

  const data = results.map((r) => ({
    name: STRATEGY_DISPLAY[r.strategy] ?? r.strategy,
    win_rate: parseFloat(r.win_rate.toFixed(1)),
  }))

  return (
    <ChartCard title="Win Rate by Strategy">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, left: 8, bottom: 0 }}>
          <CartesianGrid horizontal={false} stroke={THEME.border} strokeDasharray="3 3" />
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{ fill: THEME.muted, fontSize: 11 }}
            tickFormatter={(v) => `${v}%`}
            axisLine={{ stroke: THEME.border }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fill: THEME.muted, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={80}
          />
          <Tooltip content={<OracleTooltip unit="%" />} cursor={{ fill: THEME.border + '40' }} />
          <ReferenceLine x={50} stroke={THEME.muted} strokeDasharray="4 3" />
          <Bar dataKey="win_rate" name="Win Rate" radius={[0, 4, 4, 0]} maxBarSize={28}>
            {data.map((entry) => (
              <Cell
                key={entry.name}
                fill={
                  entry.win_rate >= 55 ? THEME.bull :
                  entry.win_rate >= 45 ? THEME.gold :
                  THEME.bear
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

// ── 3. Profit Factor Comparison ────────────────────────────────────────────

export function ProfitFactorChart({ results }) {
  if (!results?.length) return <EmptyChart title="Profit Factor by Strategy" />

  const data = results.map((r) => ({
    name: STRATEGY_DISPLAY[r.strategy] ?? r.strategy,
    profit_factor: parseFloat(r.profit_factor.toFixed(3)),
  }))

  const maxPF = Math.max(...data.map(d => d.profit_factor), 2)

  return (
    <ChartCard title="Profit Factor by Strategy">
      <p className="text-xs text-muted mb-3">Above 1.0 = profitable · Above 1.5 = strong</p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, left: 8, bottom: 0 }}>
          <CartesianGrid horizontal={false} stroke={THEME.border} strokeDasharray="3 3" />
          <XAxis
            type="number"
            domain={[0, Math.ceil(maxPF * 1.1)]}
            tick={{ fill: THEME.muted, fontSize: 11 }}
            axisLine={{ stroke: THEME.border }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fill: THEME.muted, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={80}
          />
          <Tooltip content={<OracleTooltip />} cursor={{ fill: THEME.border + '40' }} />
          <ReferenceLine x={1} stroke={THEME.bear} strokeDasharray="4 3" label={{ value: '1.0', fill: THEME.bear, fontSize: 10 }} />
          <ReferenceLine x={1.5} stroke={THEME.bull} strokeDasharray="4 3" label={{ value: '1.5', fill: THEME.bull, fontSize: 10 }} />
          <Bar dataKey="profit_factor" name="Profit Factor" radius={[0, 4, 4, 0]} maxBarSize={28}>
            {data.map((entry) => (
              <Cell
                key={entry.name}
                fill={
                  entry.profit_factor >= 1.5 ? THEME.bull :
                  entry.profit_factor >= 1.0 ? THEME.gold :
                  THEME.bear
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

// ── 4. Combined Overview Chart ─────────────────────────────────────────────
// Grouped bar: Accuracy + WinRate side by side for all strategies

export function OverviewChart({ results }) {
  if (!results?.length) return <EmptyChart title="Strategy Overview" />

  const data = results.map((r) => ({
    name: STRATEGY_DISPLAY[r.strategy] ?? r.strategy,
    Accuracy: parseFloat(r.accuracy.toFixed(1)),
    'Win Rate': parseFloat(r.win_rate.toFixed(1)),
  }))

  return (
    <ChartCard title="Strategy Overview — Accuracy vs Win Rate">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }} barCategoryGap="30%">
          <CartesianGrid vertical={false} stroke={THEME.border} strokeDasharray="3 3" />
          <XAxis
            dataKey="name"
            tick={{ fill: THEME.muted, fontSize: 12 }}
            axisLine={{ stroke: THEME.border }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: THEME.muted, fontSize: 11 }}
            tickFormatter={(v) => `${v}%`}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            content={<OracleTooltip unit="%" />}
            cursor={{ fill: THEME.border + '30' }}
          />
          <Legend
            wrapperStyle={{ fontSize: 12, color: THEME.muted }}
          />
          <ReferenceLine y={50} stroke={THEME.muted} strokeDasharray="4 3" />
          <Bar dataKey="Accuracy"  fill={THEME.gold}  radius={[3, 3, 0, 0]} maxBarSize={32} />
          <Bar dataKey="Win Rate"  fill={THEME.blue}  radius={[3, 3, 0, 0]} maxBarSize={32} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
