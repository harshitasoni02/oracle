import { useState, useEffect, useRef, useCallback } from 'react'

const MAX_RECONNECT_DELAY = 30_000
const PING_INTERVAL = 25_000

export default function useLivePrices(metal) {
  const [data, setData] = useState(null)
  const [isConnected, setIsConnected] = useState(false)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [sentimentData, setSentimentData] = useState({})

  const wsRef = useRef(null)
  const reconnectDelay = useRef(1000)
  const reconnectTimer = useRef(null)
  const pingTimer = useRef(null)
  const metalRef = useRef(metal)

  // Reset data when metal changes
  useEffect(() => {
    metalRef.current = metal
    setData(null)
  }, [metal])

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const basePath = import.meta.env.VITE_BASE_PATH || '/'
    const wsPath = basePath === '/' ? '/ws/prices/' : `${basePath}ws/prices/`
    const url = `${proto}//${window.location.host}${wsPath}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      reconnectDelay.current = 1000

      // Start ping keep-alive
      pingTimer.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, PING_INTERVAL)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'pong') return
        if (msg.type === 'price_update' && msg.metals) {
          const metalData = msg.metals[metalRef.current]
          if (metalData) {
            setData(metalData)
            setLastUpdate(new Date(msg.timestamp))
          }
        }
        if (msg.type === 'sentiment_update' && msg.metal) {
          setSentimentData(prev => ({ ...prev, [msg.metal]: msg }))
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = () => {
      setIsConnected(false)
      clearInterval(pingTimer.current)

      // Reconnect with exponential backoff
      reconnectTimer.current = setTimeout(() => {
        reconnectDelay.current = Math.min(reconnectDelay.current * 2, MAX_RECONNECT_DELAY)
        connect()
      }, reconnectDelay.current)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      clearInterval(pingTimer.current)
      if (wsRef.current) {
        wsRef.current.onclose = null // prevent reconnect on unmount
        wsRef.current.close()
      }
    }
  }, [connect])

  return { data, isConnected, lastUpdate, sentimentData }
}
