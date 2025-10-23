"use client"

import { useEffect, useState, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface PriceUpdate {
  symbol: string
  // price may be NaN when unavailable/invalid
  price?: number | null
  timestamp: string
}

const POLL_INTERVAL_MS = 5000
const SYMBOLS = ["BTC", "ETH", "cUSD"]

function toBackendSymbol(symbol: string): string {
  const key = symbol.trim().toLowerCase()
  if (key === "btc") return "bitcoin"
  if (key === "eth") return "ethereum"
  if (key === "cusd") return "cusd"
  return key
}

export function LiveTicker() {
  const [updates, setUpdates] = useState<PriceUpdate[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

    let mounted = true

    async function fetchAll() {
      try {
        const fetches = SYMBOLS.map(async (sym) => {
          const backend = toBackendSymbol(sym)
          const res = await fetch(`${apiUrl}/prices/${backend}/latest`)
          if (!res.ok) return null
          const j = await res.json()
          return {
            symbol: sym,
            price: j?.price != null ? Number(j.price) : NaN,
            timestamp: j?.timestamp || new Date().toISOString(),
          } as PriceUpdate
        })

        const results = await Promise.all(fetches)

        if (!mounted) return

        const valid = results.filter((r) => r != null) as PriceUpdate[]
        if (valid.length > 0) {
          setUpdates((prev) => {
            const merged = [...valid.reverse(), ...prev] // latest first
            return merged.slice(0, 10)
          })
        }

        setIsConnected(true)
      } catch (err) {
        console.error("[v1] Polling error", err)
        setIsConnected(false)
      }
    }

    // initial fetch
    fetchAll()

    // start interval
    timerRef.current = window.setInterval(fetchAll, POLL_INTERVAL_MS)

    return () => {
      mounted = false
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [])

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Live Price Updates</CardTitle>
          <Badge variant={isConnected ? "default" : "secondary"}>{isConnected ? "Connected" : "Disconnected"}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        {updates.length === 0 ? (
          <p className="text-sm text-muted-foreground">Waiting for price updates...</p>
        ) : (
          <div className="space-y-2">
            {updates.map((update, index) => {
              const hasValidPrice = typeof update.price === "number" && Number.isFinite(update.price)
              const priceDisplay = hasValidPrice
                ? `$${update.price!.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                : "N/A"
              const timeDisplay = update.timestamp ? new Date(update.timestamp).toLocaleTimeString() : "-"
              return (
                <div
                  key={`${update.symbol}-${update.timestamp}-${index}`}
                  className="flex items-center justify-between rounded-lg border border-border bg-muted/50 p-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-semibold">{update.symbol}</span>
                    <span className="text-lg font-bold">{priceDisplay}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">{timeDisplay}</span>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
