"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface PriceUpdate {
  symbol: string
  // price may be NaN when unavailable/invalid
  price?: number | null
  timestamp: string
}

export function LiveTicker() {
  const [updates, setUpdates] = useState<PriceUpdate[]>([])
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    const wsUrl = apiUrl.replace("http", "ws")
    const ws = new WebSocket(`${wsUrl}/ws/prices`)

    ws.onopen = () => {
      setIsConnected(true)
      console.log("[v0] WebSocket connected")
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        // ignore ping or other control messages
        if (!data || typeof data !== "object") return
        if (data.type === "ping") return

        // require at least a symbol
        if (!data.symbol) return

        // normalize timestamp (fallback to now)
        const ts = data.timestamp || new Date().toISOString()

        // attempt to coerce price to number; allow NaN to represent unavailable price
        const rawPrice = data.price
        const priceNum = typeof rawPrice === "string" || typeof rawPrice === "number" ? Number(rawPrice) : NaN

        const update: PriceUpdate = {
          symbol: String(data.symbol),
          price: Number.isFinite(priceNum) ? priceNum : NaN,
          timestamp: ts,
        }

        console.log("[v0] Received price update:", update)
        setUpdates((prev: PriceUpdate[]) => [update, ...prev].slice(0, 10))
      } catch (err) {
        console.error("[v0] Failed to parse WS message", err)
      }
    }

    ws.onerror = (error) => {
      console.error("[v0] WebSocket error:", error)
      setIsConnected(false)
    }

    ws.onclose = () => {
      setIsConnected(false)
      console.log("[v0] WebSocket disconnected")
    }

    return () => {
      ws.close()
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
