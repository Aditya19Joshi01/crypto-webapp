"use client"

import { useQuery } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { TrendingUp, TrendingDown } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"

const symbols = ["BTC", "ETH", "cUSD"]

function toBackendSymbol(symbol: string): string {
  const key = symbol.trim().toLowerCase()
  if (key === "btc") return "bitcoin"
  if (key === "eth") return "ethereum"
  if (key === "cusd" || key === "cusd") return "cusd"
  return key
}

async function fetchLatestWithChange(symbol: string) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const backendSymbol = toBackendSymbol(symbol)

  // fetch latest
  const latestRes = await fetch(`${apiUrl}/prices/${backendSymbol}/latest`)
  if (!latestRes.ok) throw new Error("Failed to fetch latest price")
  const latestJson = await latestRes.json()

  // fetch up to 2 historical entries to compute a short-term change (fallback when available)
  const histRes = await fetch(`${apiUrl}/prices/${backendSymbol}?limit=2`)
  let change = null
  if (histRes.ok) {
    try {
      const histJson = await histRes.json()
      const prices = histJson?.prices || []
      // prices ordered desc: [latest, previous, ...]
      if (prices.length >= 2) {
        const latestPrice = Number(prices[0]?.price)
        const prevPrice = Number(prices[1]?.price)
        if (Number.isFinite(latestPrice) && Number.isFinite(prevPrice) && prevPrice !== 0) {
          change = ((latestPrice - prevPrice) / Math.abs(prevPrice)) * 100
        }
      }
    } catch (e) {
      // ignore historical parse errors and leave change as null
    }
  }

  return {
    symbol: latestJson.symbol || backendSymbol,
    name: latestJson.name,
    price: latestJson.price,
    timestamp: latestJson.timestamp,
    provider: latestJson.provider,
    change_24h: change,
  }
}

function PriceCard({ symbol }: { symbol: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["price", symbol],
    queryFn: () => fetchLatestWithChange(symbol),
  })

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">{symbol}</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-8 w-32" />
          <Skeleton className="mt-2 h-4 w-24" />
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">{symbol}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">Failed to load</p>
        </CardContent>
      </Card>
    )
  }

  const price = data?.price != null ? Number(data.price) : 0
  const change = data?.change_24h != null ? Number(data.change_24h) : null
  const isPositive = change != null ? change >= 0 : true

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">{symbol}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <p className="text-3xl font-bold">
            ${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          {change != null ? (
            <div className="flex items-center gap-1">
              {isPositive ? (
                <TrendingUp className="h-4 w-4 text-chart-4" />
              ) : (
                <TrendingDown className="h-4 w-4 text-destructive" />
              )}
              <span className={`text-sm font-medium ${isPositive ? "text-chart-4" : "text-destructive"}`}>
                {isPositive ? "+" : ""}
                {change.toFixed(2)}%
              </span>
              <span className="text-sm text-muted-foreground">24h</span>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">24h change unavailable</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export function PriceSummaryCards() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Market Overview</h2>
      <div className="grid gap-4 md:grid-cols-3">
        {symbols.map((symbol) => (
          <PriceCard key={symbol} symbol={symbol} />
        ))}
      </div>
      <Alert>
        <AlertDescription>
          Prices are fetched from the backend API. Make sure your API is running at{" "}
          {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
        </AlertDescription>
      </Alert>
    </div>
  )
}
