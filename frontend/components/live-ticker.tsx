"use client"

import { useEffect, useState, useRef } from "react"
import { useQuery } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { getCoins, toUiTicker, getMode } from "@/lib/api"

interface PriceUpdate {
  symbol: string
  // price may be NaN when unavailable/invalid
  price?: number | null
  timestamp: string
}

export function LiveTicker() {
  const [updates, setUpdates] = useState<PriceUpdate[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const timerRef = useRef<number | null>(null)

  // fetch dynamic coins list
  const { data: coins, isLoading } = useQuery({ queryKey: ["coins"], queryFn: getCoins })
  const coinList = coins || []

  // fetch mode/config from backend (live_mode, poll_interval)
  const { data: modeData } = useQuery({ queryKey: ["mode"], queryFn: getMode })

  useEffect(() => {
    let mounted = true
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

    async function fetchAll() {
      try {
        const symbols = coinList.map((c: any) => c.symbol)
        if (symbols.length === 0) return

        const fetches = symbols.map(async (backendSymbol) => {
          const res = await fetch(`${apiUrl}/prices/${backendSymbol}/latest`)
          if (!res.ok) return null
          const j = await res.json()
          return {
            symbol: toUiTicker(backendSymbol, j?.name),
            price: j?.price != null ? Number(j.price) : NaN,
            timestamp: j?.timestamp || new Date().toISOString(),
          } as PriceUpdate
        })

        const results = await Promise.all(fetches)
        if (!mounted) return
        const valid = results.filter((r) => r != null) as PriceUpdate[]
        if (valid.length > 0) {
          setUpdates((prev) => {
            const merged = [...valid.reverse(), ...prev]
            return merged.slice(0, 10)
          })
        }

        setIsConnected(true)
      } catch (err) {
        console.error("[v1] Polling error", err)
        setIsConnected(false)
      }
    }

    // Determine whether we should poll and at what interval.
    // Backend provides `poll_interval` in seconds and `live_mode` boolean via /mode.
    const isLive = Boolean(modeData?.live_mode)
    const pollSeconds = Number(modeData?.poll_interval ?? 5)
    const pollMs = Math.max(1000, Math.round(pollSeconds * 1000))

    // initial fetch + start interval only when coins are available and live mode enabled
    if (!isLoading && coinList.length > 0 && isLive) {
      fetchAll()
      timerRef.current = window.setInterval(fetchAll, pollMs)
    }

    return () => {
      mounted = false
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [coinList, isLoading, modeData])

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
