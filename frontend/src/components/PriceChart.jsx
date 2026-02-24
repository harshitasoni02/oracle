import React, { useEffect, useRef, useState } from 'react'
import { createChart, CrosshairMode, LineStyle } from 'lightweight-charts'

const OVERLAYS = [
  { key: 'sma20',   label: 'SMA 20',  color: '#F0A500', width: 1 },
  { key: 'sma50',   label: 'SMA 50',  color: '#58A6FF', width: 1 },
  { key: 'sma200',  label: 'SMA 200', color: '#BC8CFF', width: 2 },
  { key: 'ema12',   label: 'EMA 12',  color: '#79C0FF', width: 1 },
  { key: 'ema26',   label: 'EMA 26',  color: '#D2A8FF', width: 1 },
]

export default function PriceChart({ bars, indicators, metal, timeframe }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const candleRef = useRef(null)
  const volumeRef = useRef(null)
  const overlaySeriesRef = useRef({})
  const bbSeriesRef = useRef({})

  const [activeOverlays, setActiveOverlays] = useState({ sma20: true, sma50: true, sma200: false, ema12: false, ema26: false })
  const [showBB, setShowBB] = useState(false)
  const [showVolume, setShowVolume] = useState(true)

  // Create chart on mount
  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#0D1117' },
        textColor: '#8B949E',
        fontSize: 11,
        fontFamily: 'Inter, system-ui, sans-serif',
      },
      grid: {
        vertLines: { color: '#1C2128', style: LineStyle.Dotted },
        horzLines: { color: '#1C2128', style: LineStyle.Dotted },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#6E7681', width: 1, style: LineStyle.Dashed },
        horzLine: { color: '#6E7681', width: 1, style: LineStyle.Dashed },
      },
      rightPriceScale: { borderColor: '#30363D' },
      timeScale: {
        borderColor: '#30363D',
        timeVisible: true,
        secondsVisible: false,
        fixLeftEdge: false,
        fixRightEdge: false,
      },
      handleScroll: true,
      handleScale: true,
    })

    // Main candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#3FB950',
      downColor: '#F85149',
      borderUpColor: '#3FB950',
      borderDownColor: '#F85149',
      wickUpColor: '#3FB950',
      wickDownColor: '#F85149',
    })

    // Volume histogram (separate pane)
    const volumeSeries = chart.addHistogramSeries({
      color: '#30363D',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
      scaleMargins: { top: 0.85, bottom: 0 },
    })

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    })

    // SMA / EMA overlay series
    const overlaySeries = {}
    OVERLAYS.forEach(({ key, color, width }) => {
      overlaySeries[key] = chart.addLineSeries({
        color,
        lineWidth: width,
        visible: false,
        priceLineVisible: false,
        lastValueVisible: false,
      })
    })

    // Bollinger Band series
    const bbSeries = {
      upper: chart.addLineSeries({ color: '#6E4DFF', lineWidth: 1, lineStyle: LineStyle.Dashed, visible: false, priceLineVisible: false, lastValueVisible: false }),
      middle: chart.addLineSeries({ color: '#6E4DFF', lineWidth: 1, visible: false, priceLineVisible: false, lastValueVisible: false }),
      lower: chart.addLineSeries({ color: '#6E4DFF', lineWidth: 1, lineStyle: LineStyle.Dashed, visible: false, priceLineVisible: false, lastValueVisible: false }),
    }

    chartRef.current = chart
    candleRef.current = candleSeries
    volumeRef.current = volumeSeries
    overlaySeriesRef.current = overlaySeries
    bbSeriesRef.current = bbSeries

    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [])

  // Update candle + volume data when bars change
  useEffect(() => {
    if (!candleRef.current || !bars?.length) return

    const toUnix = (ts) => Math.floor(new Date(ts).getTime() / 1000)

    const candleData = bars
      .filter(b => b.close_usd)
      .map(b => ({
        time: toUnix(b.timestamp),
        open: b.open_usd,
        high: b.high_usd,
        low: b.low_usd,
        close: b.close_usd,
      }))
      .sort((a, b) => a.time - b.time)

    const volumeData = bars
      .filter(b => b.volume != null)
      .map(b => ({
        time: toUnix(b.timestamp),
        value: b.volume,
        color: b.close_usd >= b.open_usd ? '#2EA04310' : '#F8514910',
      }))
      .sort((a, b) => a.time - b.time)

    candleRef.current.setData(candleData)
    volumeRef.current.setData(volumeData)

    // Compute and set SMA/EMA overlays from bars
    if (candleData.length > 20) {
      const closes = candleData.map(d => d.close)
      const times = candleData.map(d => d.time)

      const calcSMA = (n) => closes.map((_, i) => {
        if (i < n - 1) return null
        const slice = closes.slice(i - n + 1, i + 1)
        return { time: times[i], value: slice.reduce((a, b) => a + b, 0) / n }
      }).filter(Boolean)

      const calcEMA = (n) => {
        const k = 2 / (n + 1)
        const result = []
        let ema = closes[0]
        closes.forEach((close, i) => {
          ema = close * k + ema * (1 - k)
          if (i >= n - 1) result.push({ time: times[i], value: ema })
        })
        return result
      }

      const overlayData = {
        sma20: calcSMA(20),
        sma50: calcSMA(50),
        sma200: calcSMA(200),
        ema12: calcEMA(12),
        ema26: calcEMA(26),
      }

      OVERLAYS.forEach(({ key }) => {
        overlaySeriesRef.current[key]?.setData(overlayData[key] || [])
      })
    }

    // Bollinger Bands
    if (candleData.length > 20) {
      const n = 20, k = 2
      const bbData = candleData.map((d, i) => {
        if (i < n - 1) return null
        const slice = bars.slice(i - n + 1, i + 1).map(b => b.close_usd)
        const mean = slice.reduce((a, b) => a + b, 0) / n
        const std = Math.sqrt(slice.reduce((a, b) => a + (b - mean) ** 2, 0) / n)
        return { time: d.time, upper: mean + k * std, middle: mean, lower: mean - k * std }
      }).filter(Boolean)

      bbSeriesRef.current.upper?.setData(bbData.map(d => ({ time: d.time, value: d.upper })))
      bbSeriesRef.current.middle?.setData(bbData.map(d => ({ time: d.time, value: d.middle })))
      bbSeriesRef.current.lower?.setData(bbData.map(d => ({ time: d.time, value: d.lower })))
    }

    chartRef.current?.timeScale().fitContent()
  }, [bars])

  // Toggle overlays visibility
  useEffect(() => {
    OVERLAYS.forEach(({ key }) => {
      overlaySeriesRef.current[key]?.applyOptions({ visible: activeOverlays[key] })
    })
  }, [activeOverlays])

  useEffect(() => {
    Object.values(bbSeriesRef.current).forEach(s => s?.applyOptions({ visible: showBB }))
  }, [showBB])

  useEffect(() => {
    volumeRef.current?.applyOptions({ visible: showVolume })
  }, [showVolume])

  const toggleOverlay = (key) => setActiveOverlays(prev => ({ ...prev, [key]: !prev[key] }))

  return (
    <div className="flex flex-col gap-2">
      {/* Overlay toggles */}
      <div className="flex flex-wrap gap-2 px-1">
        {OVERLAYS.map(({ key, label, color }) => (
          <button
            key={key}
            onClick={() => toggleOverlay(key)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all ${
              activeOverlays[key]
                ? 'bg-surface border border-border opacity-100'
                : 'bg-transparent border border-border/40 opacity-40'
            }`}
          >
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
            {label}
          </button>
        ))}
        <button
          onClick={() => setShowBB(v => !v)}
          className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all ${
            showBB ? 'bg-surface border border-border' : 'bg-transparent border border-border/40 opacity-40'
          }`}
        >
          <span className="w-2 h-2 rounded-full bg-purple-500" />
          BB (20,2)
        </button>
        <button
          onClick={() => setShowVolume(v => !v)}
          className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all ${
            showVolume ? 'bg-surface border border-border' : 'bg-transparent border border-border/40 opacity-40'
          }`}
        >
          <span className="w-2 h-2 rounded-full bg-border" />
          Volume
        </button>
      </div>

      {/* Chart container */}
      <div
        ref={containerRef}
        className="w-full rounded-lg overflow-hidden border border-border"
        style={{ height: '380px' }}
      />

      <p className="text-xs text-muted px-1">
        Prices in USD/oz · Source: COMEX Futures (GC=F / SI=F) · Not financial advice
      </p>
    </div>
  )
}
