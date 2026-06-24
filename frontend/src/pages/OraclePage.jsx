import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { BarChart2, AlertTriangle, FlaskConical } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { api } from '../services/api.js'
import useLivePrices from '../hooks/useLivePrices'
import MetalTimeframeBar from '../components/MetalTimeframeBar'
import CurrentPriceCard from '../components/CurrentPriceCard'
import PriceChart from '../components/PriceChart'
import { RSIChart, MACDChart, StochasticChart } from '../components/IndicatorSubChart'
import SignalTable from '../components/SignalTable'
import PredictionCards from '../components/PredictionCards'
import SentimentCard from '../components/SentimentCard'

const REFETCH_FAST = 30 * 1000      // 30s when WS disconnected
const REFETCH_SLOW = 60 * 1000      // 60s when WS connected (backup)

export default function OraclePage() {
  const [metal, setMetal] = useState('gold')
  const [timeframe, setTimeframe] = useState('1m')
  const [activeSubChart, setActiveSubChart] = useState('rsi')

  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: liveData, isConnected: isLive, lastUpdate, sentimentData } = useLivePrices(metal)

  const priceQuery = useQuery({
    queryKey: ['price', metal],
    queryFn: () => api.getPrice(metal),
    refetchInterval: isLive ? REFETCH_SLOW : REFETCH_FAST,
    retry: 2,
  })

  const historicalQuery = useQuery({
    queryKey: ['historical', metal, timeframe],
    queryFn: () => api.getHistorical(metal, timeframe),
    staleTime: 2 * 60 * 1000,
  })

  const indicatorsQuery = useQuery({
    queryKey: ['indicators', metal, timeframe],
    queryFn: () => api.getIndicators(metal, timeframe),
    staleTime: 5 * 60 * 1000,
  })

  const predictionsQuery = useQuery({
    queryKey: ['predictions', metal],
    queryFn: () => api.getPredictions(metal),
    staleTime: 10 * 60 * 1000,
  })

  const sentimentQuery = useQuery({
    queryKey: ['sentiment', metal],
    queryFn: () => api.getSentiment(metal),
    staleTime: 30 * 60 * 1000,  // 30 min — WS keeps it fresh
  })

  const refreshMutation = useMutation({
    mutationFn: api.triggerRefresh,
    onSuccess: () => {
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['price', metal] })
        qc.invalidateQueries({ queryKey: ['historical', metal] })
        qc.invalidateQueries({ queryKey: ['indicators', metal] })
        qc.invalidateQueries({ queryKey: ['predictions', metal] })
        qc.invalidateQueries({ queryKey: ['sentiment', metal] })
      }, 35_000)  // wait 35s for background tasks to complete
    },
  })

  const handleMetalChange = (m) => {
    setMetal(m)
    setTimeframe('1m')
  }

  const bars = historicalQuery.data || []
  const indicators = indicatorsQuery.data || null
  const predictions = predictionsQuery.data || []
  const price = liveData || priceQuery.data || null
  const sentiment = sentimentData?.[metal] ?? sentimentQuery.data ?? null

  const isLoading = priceQuery.isLoading && historicalQuery.isLoading

  return (
    <div className="min-h-screen bg-bg text-white">
      {/* Header */}
      <header className="border-b border-border bg-surface/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-[1600px] mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart2 size={20} className="text-gold" />
            <span className="font-bold text-white text-lg">Shizuha Oracle</span>
            <span className="text-xs text-muted bg-border px-2 py-0.5 rounded">Gold & Silver Spot Prices</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted">
            <button
              onClick={() => navigate('/backtesting')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-muted hover:text-white hover:bg-border/60 transition-all"
            >
              <FlaskConical size={13} />
              <span className="hidden sm:block">Backtesting</span>
            </button>
            <span className="hidden sm:block text-border">|</span>
            <span className="hidden sm:block">India focus · INR prices</span>
            <span className={`w-1.5 h-1.5 rounded-full ${isLive ? 'bg-bull live-dot' : 'bg-muted'}`} />
            <span>{isLive ? 'Live' : 'Polling'}</span>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-4 py-5 space-y-5">
        {/* Metal + Timeframe selector */}
        <MetalTimeframeBar
          metal={metal}
          timeframe={timeframe}
          onMetalChange={handleMetalChange}
          onTimeframeChange={setTimeframe}
        />

        {/* Error banners */}
        {(priceQuery.error || historicalQuery.error) && (
          <div className="flex items-center gap-2 bg-bear/10 border border-bear/30 text-bear rounded-lg px-4 py-2 text-sm">
            <AlertTriangle size={16} />
            <span>
              Could not fetch data. The backend may be starting up or data is not yet available.
              <button onClick={() => refreshMutation.mutate()} className="ml-2 underline">
                Trigger refresh
              </button>
            </span>
          </div>
        )}

        {/* Main layout */}
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-5">
          {/* Left column: chart + sub-charts */}
          <div className="space-y-4">
            {/* Current price */}
            <CurrentPriceCard
              metal={metal}
              price={price}
              onRefresh={() => refreshMutation.mutate()}
              isRefreshing={refreshMutation.isPending}
              isLive={isLive}
              lastUpdate={lastUpdate}
            />

            {/* Main chart */}
            <div className="bg-surface border border-border rounded-xl p-4">
              <PriceChart
                bars={bars}
                indicators={indicators}
                metal={metal}
                timeframe={timeframe}
              />
            </div>

            {/* Sub-chart selector + chart */}
            {bars.length > 0 && (
              <div className="bg-surface border border-border rounded-xl p-4">
                <div className="flex gap-2 mb-3">
                  {[
                    { key: 'rsi', label: 'RSI' },
                    { key: 'macd', label: 'MACD' },
                    { key: 'stoch', label: 'Stochastic' },
                  ].map(s => (
                    <button
                      key={s.key}
                      onClick={() => setActiveSubChart(s.key)}
                      className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                        activeSubChart === s.key
                          ? 'bg-border text-white'
                          : 'text-muted hover:text-white'
                      }`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
                {activeSubChart === 'rsi' && <RSIChart bars={bars} />}
                {activeSubChart === 'macd' && <MACDChart bars={bars} />}
                {activeSubChart === 'stoch' && <StochasticChart bars={bars} />}
              </div>
            )}

            {/* Predictions */}
            <div className="bg-surface border border-border rounded-xl p-4">
              <h2 className="text-base font-semibold text-white mb-4">Price Predictions</h2>
              <PredictionCards predictions={predictions} metal={metal} />
            </div>
          </div>

          {/* Right column: signal table */}
          <div className="space-y-4">
            <SignalTable indicators={indicators} />

            <SentimentCard sentiment={sentiment} />

            {/* India market note */}
            <div className="bg-surface border border-border rounded-xl p-4">
              <h3 className="text-sm font-semibold text-white mb-3">India Market Factors</h3>
              <div className="space-y-2 text-xs text-muted">
                <div className="flex justify-between">
                  <span>Basic Customs Duty</span>
                  <span className="mono text-white">6%</span>
                </div>
                <div className="flex justify-between">
                  <span>AIDC (Agri Cess)</span>
                  <span className="mono text-white">5%</span>
                </div>
                <div className="flex justify-between">
                  <span>GST</span>
                  <span className="mono text-white">3%</span>
                </div>
                <div className="flex justify-between">
                  <span>Effective MCX Premium</span>
                  <span className="mono text-white">~6.4% (Gold) / ~2.1% (Silver)</span>
                </div>
                <div className="flex justify-between">
                  <span>Making charges</span>
                  <span className="mono text-white">8–25%</span>
                </div>
                <div className="border-t border-border pt-2 mt-2 text-muted/70 text-xs leading-relaxed">
                  MCX prices = International spot + import duties + GST + exchange premium.
                  Wedding season (Oct–Mar) and Dhanteras/Akshaya Tritiya boost demand.
                  Duty was reduced from 15% to 6% in Budget 2024.
                </div>
              </div>
            </div>

            {/* Key indicators summary */}
            {indicators && (
              <div className="bg-surface border border-border rounded-xl p-4">
                <h3 className="text-sm font-semibold text-white mb-3">Key Levels</h3>
                <div className="space-y-2 text-xs">
                  {[
                    { label: 'Current', value: indicators.current_price, color: '#F0F6FC' },
                    { label: 'SMA 20', value: indicators.sma20, color: '#F0A500' },
                    { label: 'SMA 50', value: indicators.sma50, color: '#58A6FF' },
                    { label: 'SMA 200', value: indicators.sma200, color: '#BC8CFF' },
                    { label: 'BB Upper', value: indicators.bb_upper, color: '#6E4DFF' },
                    { label: 'BB Lower', value: indicators.bb_lower, color: '#6E4DFF' },
                  ].map(({ label, value, color }) => value && (
                    <div key={label} className="flex justify-between">
                      <span className="text-muted">{label}</span>
                      <span className="mono" style={{ color }}>${value.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Data quality note */}
            <div className="bg-surface border border-border rounded-xl p-3 text-xs text-muted space-y-1">
              <p className="font-medium text-white text-xs">Data Sources</p>
              <p>Gold: XAU/USD Spot (GoldAPI)</p>
              <p>Silver: XAG/USD Spot (GoldAPI)</p>
              <p>Historical: COMEX futures via yfinance</p>
              <p>USD/INR: Forex spot (USDINR=X)</p>
              <p>Prices: live via WebSocket (~5-10s)</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
