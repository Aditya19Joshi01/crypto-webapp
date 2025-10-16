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
  if (key === "cusd") return "cusd"
  return key
}

async function fetchLatestPrice(symbol: string) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const backendSymbol = toBackendSymbol(symbol)
  const response = await fetch(`${apiUrl}/prices/${backendSymbol}/latest`)
  if (!response.ok) throw new Error("Failed to fetch price")
  return response.json()
}

function PriceCard({ symbol }: { symbol: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["price", symbol],
    queryFn: () => fetchLatestPrice(symbol),
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
  const change = data?.change_24h != null ? Number(data.change_24h) : 0
  const isPositive = change >= 0

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
