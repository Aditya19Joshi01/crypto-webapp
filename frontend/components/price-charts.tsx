"use client"

import { useQuery } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"
import { Alert, AlertDescription } from "@/components/ui/alert"

const symbols = ["BTC", "ETH", "cUSD"]

async function fetchPriceHistory(symbol: string) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const response = await fetch(`${apiUrl}/prices/${symbol}`)
  if (!response.ok) throw new Error("Failed to fetch price history")
  return response.json()
}

function PriceChart({ symbol }: { symbol: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["priceHistory", symbol],
    queryFn: () => fetchPriceHistory(symbol),
  })

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{symbol} Price History</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (error || !Array.isArray(data) || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{symbol} Price History</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>Failed to load price history for {symbol}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    )
  }

  // Prepare chart data and calculate min/max for tight axis bounds:
  const chartData = data
    .map((item: any) => {
      if (!item || item.price == null || !item.timestamp) return null
      return {
        timestamp: new Date(item.timestamp).getTime(),
        price: Number(item.price),
      }
    })
    .filter(Boolean)

  // Calculate min and max for 'nice' y-axis bounds
  const prices = chartData.map((item: any) => item.price)
  const minPrice = Math.min(...prices)
  const maxPrice = Math.max(...prices)
  // Add some buffer around min/max so line is not cut off
  const yDomain = [
    Math.floor(minPrice - (maxPrice - minPrice) * 0.05),
    Math.ceil(maxPrice + (maxPrice - minPrice) * 0.05)
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>{symbol} Price History</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis
              dataKey="timestamp"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={ts => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              tick={{ fill: "hsl(var(--muted-foreground))" }}
            />
            <YAxis
              type="number"
              domain={[
                (dataMin: number) => Math.floor(dataMin - 10),
                (dataMax: number) => Math.ceil(dataMax + 10),
              ]}
              tick={{ fill: "hsl(var(--muted-foreground))" }}
            />
            <Tooltip
              labelFormatter={(ts) => new Date(ts).toLocaleString()}
              contentStyle={{
                backgroundColor: "hsl(var(--popover))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "0.5rem",
              }}
            />
            <Line
              type="monotone"
              dataKey="price"
              stroke="hsl(var(--chart-1))"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export function PriceCharts() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Historical Charts</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        {symbols.map((symbol) => (
          <PriceChart key={symbol} symbol={symbol} />
        ))}
      </div>
    </div>
  )
}
