import React, { useRef, useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, Minus, RefreshCw } from 'lucide-react'
import { format } from 'date-fns'

function fmt(n, dec = 2) {
  if (n == null) return '—'
  return new Intl.NumberFormat('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(n)
}

function fmtUSD(n) {
  if (n == null) return '—'
  return '$' + fmt(n, 2)
}

function fmtINR(n, dec = 0) {
  if (n == null) return '—'
  return '₹' + fmt(n, dec)
}

export default function CurrentPriceCard({ metal, price, onRefresh, isRefreshing, isLive, lastUpdate }) {
  const prevPriceRef = useRef(null)
  const [flash, setFlash] = useState(null) // 'up' | 'down' | null

  useEffect(() => {
    if (!price?.price_usd) return
    const prev = prevPriceRef.current
    prevPriceRef.current = price.price_usd
    if (prev === null || prev === price.price_usd) return
    setFlash(price.price_usd > prev ? 'up' : 'down')
    const timer = setTimeout(() => setFlash(null), 600)
    return () => clearTimeout(timer)
  }, [price?.price_usd])

  if (!price) {
    return (
      <div className="bg-surface border border-border rounded-xl p-4 flex items-center justify-between">
        <p className="text-muted text-sm">No price data yet.</p>
        <button onClick={onRefresh} disabled={isRefreshing}
          className="flex items-center gap-2 px-3 py-1.5 bg-gold/10 hover:bg-gold/20 text-gold rounded-lg text-sm font-medium transition-all disabled:opacity-50">
          <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>
    )
  }

  const isGold = metal === 'gold'
  const accentColor = isGold ? '#F0A500' : '#A0ADB7'
  const positive = price.change_24h_pct >= 0

  // MCX price — the hero number for Indian users
  const mcxPrice = isGold ? price.mcx_price_10g : price.mcx_price_kg
  const mcxUnit = isGold ? '/10g' : '/kg'
  const mcxLabel = isGold ? 'MCX Gold (per 10g)' : 'MCX Silver (per kg)'

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-3xl">{isGold ? '🥇' : '🥈'}</span>
          <div>
            <h2 className="text-xl font-bold capitalize" style={{ color: accentColor }}>
              {metal}
            </h2>
            <p className="text-xs text-muted flex items-center gap-1.5">
              {price.source === 'futures' ? 'COMEX Futures' : 'Spot Price'} · Updated {format(lastUpdate || new Date(price.updated_at || Date.now()), 'HH:mm:ss')}
              {isLive ? (
                <span className="inline-flex items-center gap-1 bg-bull/15 text-bull px-1.5 py-0.5 rounded text-[10px] font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-bull live-dot" />
                  LIVE
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 bg-muted/15 text-muted px-1.5 py-0.5 rounded text-[10px] font-medium">
                  Polling
                </span>
              )}
            </p>
          </div>
        </div>
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-surface hover:bg-border rounded-lg text-xs text-muted border border-border transition-all disabled:opacity-50"
        >
          <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* MCX India Price — hero section */}
      {mcxPrice && (
        <div className="mb-4 rounded-lg p-4" style={{ backgroundColor: accentColor + '12', border: `1px solid ${accentColor}30` }}>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-medium" style={{ color: accentColor }}>
              {mcxLabel}
            </p>
            <span className="text-[10px] px-1.5 py-0.5 rounded font-medium" style={{ backgroundColor: accentColor + '20', color: accentColor }}>
              MCX India
            </span>
          </div>
          <div className="flex items-end gap-3 flex-wrap">
            <span
              className="text-3xl font-bold mono transition-colors duration-300"
              style={{ color: flash === 'up' ? '#3FB950' : flash === 'down' ? '#F85149' : accentColor }}
            >
              {fmtINR(mcxPrice)}
            </span>
            <div className={`flex items-center gap-1 pb-1 text-sm font-medium ${positive ? 'text-bull' : 'text-bear'}`}>
              {positive ? <TrendingUp size={14} /> : price.change_24h_pct === 0 ? <Minus size={14} /> : <TrendingDown size={14} />}
              <span>{positive ? '+' : ''}{fmt(price.change_24h_pct, 2)}%</span>
            </div>
          </div>
          <p className="text-[10px] mt-1 opacity-60" style={{ color: accentColor }}>
            Per gram: {fmtINR(price.mcx_price_per_gram)}
          </p>
        </div>
      )}

      {/* International spot price */}
      <div className="mb-4">
        <p className="text-xs text-muted mb-1">International Spot (per troy oz)</p>
        <div className="flex items-end gap-3 flex-wrap">
          <span className="text-2xl font-bold mono text-white">
            {fmtUSD(price.price_usd)}
          </span>
          <span className="text-lg font-semibold mono text-muted pb-0.5">
            ({fmtINR(price.price_inr)})
          </span>
          <div className={`flex items-center gap-1 pb-0.5 text-xs font-medium ${positive ? 'text-bull' : 'text-bear'}`}>
            {positive ? <TrendingUp size={12} /> : price.change_24h_pct === 0 ? <Minus size={12} /> : <TrendingDown size={12} />}
            <span>{positive ? '+' : ''}{fmtUSD(price.change_24h_usd)}</span>
          </div>
        </div>
        <p className="text-xs text-muted mt-1">
          24h: {fmtUSD(price.low_24h_usd)} – {fmtUSD(price.high_24h_usd)}
        </p>
      </div>

      {/* Price grid */}
      <div className={`grid gap-3 ${isGold ? 'grid-cols-4' : 'grid-cols-4'}`}>
        <div className="bg-bg rounded-lg p-3">
          <p className="text-[10px] text-muted mb-1">Intl / Gram</p>
          <p className="text-sm font-semibold mono text-white">{fmtINR(price.price_per_gram_inr)}</p>
        </div>
        {isGold ? (
          <div className="bg-bg rounded-lg p-3">
            <p className="text-[10px] text-muted mb-1">Intl / 10g</p>
            <p className="text-sm font-semibold mono text-white">{fmtINR(price.price_per_10g_inr)}</p>
          </div>
        ) : (
          <div className="bg-bg rounded-lg p-3">
            <p className="text-[10px] text-muted mb-1">Intl / Kg</p>
            <p className="text-sm font-semibold mono text-white">{fmtINR(price.price_per_kg_inr)}</p>
          </div>
        )}
        <div className="bg-bg rounded-lg p-3">
          <p className="text-[10px] text-muted mb-1">MCX / Gram</p>
          <p className="text-sm font-semibold mono" style={{ color: accentColor }}>{fmtINR(price.mcx_price_per_gram)}</p>
        </div>
        <div className="bg-bg rounded-lg p-3">
          <p className="text-[10px] text-muted mb-1">USD/INR</p>
          <p className="text-sm font-semibold mono text-white">{fmt(price.usdinr, 2)}</p>
        </div>
      </div>

      <p className="text-[10px] text-muted mt-3 border-t border-border pt-2">
        MCX India prices include import duty (6% + 5% AIDC) and GST (3%). Actual jewellery prices include additional making charges (8-25%).
      </p>
    </div>
  )
}
