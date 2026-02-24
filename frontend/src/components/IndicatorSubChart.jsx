import React, { useMemo } from 'react'
import {
  ResponsiveContainer, ComposedChart, Line, Bar, ReferenceLine,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { format } from 'date-fns'

const chartStyle = {
  backgroundColor: '#0D1117',
}

const CustomTooltip = ({ active, payload, label, unit }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface border border-border rounded p-2 text-xs">
      <p className="text-muted mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: <span className="mono">{typeof p.value === 'number' ? p.value.toFixed(2) : p.value}</span>{unit || ''}
        </p>
      ))}
    </div>
  )
}

function prepareData(bars) {
  return bars.map(b => ({
    ...b,
    t: format(new Date(b.timestamp), 'MMM dd'),
  }))
}

// ── RSI Chart ────────────────────────────────────────────────────────────────
export function RSIChart({ bars }) {
  const data = useMemo(() => {
    if (!bars?.length) return []
    const closes = bars.map(b => b.close_usd)
    const n = 14
    const rsiValues = []
    for (let i = 0; i < closes.length; i++) {
      if (i < n) { rsiValues.push(null); continue }
      const slice = closes.slice(i - n, i + 1)
      let gains = 0, losses = 0
      for (let j = 1; j < slice.length; j++) {
        const d = slice[j] - slice[j - 1]
        if (d >= 0) gains += d; else losses += Math.abs(d)
      }
      const avgGain = gains / n
      const avgLoss = losses / n
      if (avgLoss === 0) { rsiValues.push(100); continue }
      const rs = avgGain / avgLoss
      rsiValues.push(100 - 100 / (1 + rs))
    }
    return bars.map((b, i) => ({
      t: format(new Date(b.timestamp), 'MMM dd'),
      rsi: rsiValues[i] != null ? parseFloat(rsiValues[i].toFixed(2)) : null,
    }))
  }, [bars])

  return (
    <div>
      <p className="text-xs text-muted px-2 mb-1 font-medium">RSI (14)</p>
      <ResponsiveContainer width="100%" height={100}>
        <ComposedChart data={data} style={chartStyle} margin={{ top: 4, right: 8, bottom: 0, left: 32 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1C2128" />
          <XAxis dataKey="t" hide />
          <YAxis domain={[0, 100]} ticks={[30, 50, 70]} tick={{ fill: '#8B949E', fontSize: 10 }} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={70} stroke="#F85149" strokeDasharray="4 4" strokeWidth={1} />
          <ReferenceLine y={30} stroke="#3FB950" strokeDasharray="4 4" strokeWidth={1} />
          <ReferenceLine y={50} stroke="#6E7681" strokeDasharray="2 2" strokeWidth={1} />
          <Line type="monotone" dataKey="rsi" stroke="#F0A500" dot={false} strokeWidth={1.5} name="RSI" connectNulls />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── MACD Chart ───────────────────────────────────────────────────────────────
export function MACDChart({ bars }) {
  const data = useMemo(() => {
    if (!bars?.length) return []
    const closes = bars.map(b => b.close_usd)

    const calcEMA = (arr, n) => {
      const k = 2 / (n + 1)
      const result = new Array(arr.length).fill(null)
      result[0] = arr[0]
      for (let i = 1; i < arr.length; i++) {
        result[i] = arr[i] * k + result[i - 1] * (1 - k)
      }
      return result
    }

    const ema12 = calcEMA(closes, 12)
    const ema26 = calcEMA(closes, 26)
    const macdLine = closes.map((_, i) =>
      i >= 25 ? parseFloat((ema12[i] - ema26[i]).toFixed(4)) : null
    )
    const macdFiltered = macdLine.filter(v => v != null)
    const signalEMA = calcEMA(macdFiltered, 9)

    let sigIdx = 0
    const signalLine = macdLine.map(v => {
      if (v === null) return null
      return parseFloat((signalEMA[sigIdx++] || 0).toFixed(4))
    })

    return bars.map((b, i) => ({
      t: format(new Date(b.timestamp), 'MMM dd'),
      macd: macdLine[i],
      signal: signalLine[i],
      hist: macdLine[i] != null && signalLine[i] != null
        ? parseFloat((macdLine[i] - signalLine[i]).toFixed(4))
        : null,
    }))
  }, [bars])

  return (
    <div>
      <p className="text-xs text-muted px-2 mb-1 font-medium">MACD (12, 26, 9)</p>
      <ResponsiveContainer width="100%" height={100}>
        <ComposedChart data={data} style={chartStyle} margin={{ top: 4, right: 8, bottom: 0, left: 32 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1C2128" />
          <XAxis dataKey="t" hide />
          <YAxis tick={{ fill: '#8B949E', fontSize: 10 }} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={0} stroke="#6E7681" strokeWidth={1} />
          <Bar dataKey="hist" name="Hist" fill="#3FB950"
            shape={(props) => {
              const { x, y, width, height, value } = props
              return <rect x={x} y={y} width={width} height={height}
                fill={value >= 0 ? '#3FB95050' : '#F8514950'} />
            }}
          />
          <Line type="monotone" dataKey="macd" stroke="#F0A500" dot={false} strokeWidth={1.5} name="MACD" connectNulls />
          <Line type="monotone" dataKey="signal" stroke="#FF7B72" dot={false} strokeWidth={1} name="Signal" connectNulls />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Stochastic Chart ─────────────────────────────────────────────────────────
export function StochasticChart({ bars }) {
  const data = useMemo(() => {
    if (!bars?.length) return []
    const n = 14
    return bars.map((b, i) => {
      if (i < n - 1) return { t: format(new Date(b.timestamp), 'MMM dd') }
      const slice = bars.slice(i - n + 1, i + 1)
      const lo = Math.min(...slice.map(x => x.low_usd))
      const hi = Math.max(...slice.map(x => x.high_usd))
      const k = hi === lo ? 50 : ((b.close_usd - lo) / (hi - lo)) * 100
      return {
        t: format(new Date(b.timestamp), 'MMM dd'),
        k: parseFloat(k.toFixed(2)),
      }
    })
  }, [bars])

  return (
    <div>
      <p className="text-xs text-muted px-2 mb-1 font-medium">Stochastic %K (14)</p>
      <ResponsiveContainer width="100%" height={100}>
        <ComposedChart data={data} style={chartStyle} margin={{ top: 4, right: 8, bottom: 0, left: 32 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1C2128" />
          <XAxis dataKey="t" hide />
          <YAxis domain={[0, 100]} ticks={[20, 50, 80]} tick={{ fill: '#8B949E', fontSize: 10 }} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={80} stroke="#F85149" strokeDasharray="4 4" strokeWidth={1} />
          <ReferenceLine y={20} stroke="#3FB950" strokeDasharray="4 4" strokeWidth={1} />
          <Line type="monotone" dataKey="k" stroke="#58A6FF" dot={false} strokeWidth={1.5} name="%K" connectNulls />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
