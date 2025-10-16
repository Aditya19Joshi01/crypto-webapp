"use client"

import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area } from "recharts"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

const symbols = ["BTC", "ETH", "cUSD"]

function toBackendSymbol(symbol: string): string {
  const key = symbol.trim().toLowerCase()
  if (key === "btc") return "bitcoin"
  if (key === "eth") return "ethereum"
  if (key === "cusd") return "cusd"
  return key
}

// Binance-inspired dark theme colors
const CHART_COLORS = {
  axis: "#A3A3A3", // light gray ticks/labels
  grid: "#2A2E39", // subtle grid/axis lines
  line: "#F0B90B", // Binance yellow
  areaFrom: "rgba(240, 185, 11, 0.24)",
  areaTo: "rgba(240, 185, 11, 0.04)",
  tooltipBg: "#0B0E11",
  tooltipBorder: "#2A2E39",
  label: "#E5E7EB", // near-white text
}

function formatNumberShort(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 1e12) return `${(value / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${(value / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${(value / 1e6).toFixed(2)}M`
  if (abs >= 1e3) return `${(value / 1e3).toFixed(2)}K`
  return `${value}`
}

async function fetchPriceHistory(symbol: string) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const backendSymbol = toBackendSymbol(symbol)
  const response = await fetch(`${apiUrl}/prices/${backendSymbol}`)
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
  const hasAny = prices.length > 0
  const minPrice = hasAny ? Math.min(...prices) : 0
  const maxPrice = hasAny ? Math.max(...prices) : 0
  const spread = Math.max(0.01, maxPrice - minPrice)
  // Add buffer around min/max so line is not cut off; handle flat series
  const yDomain = [
    Math.floor((minPrice - spread * 0.05) * 100) / 100,
    Math.ceil((maxPrice + spread * 0.05) * 100) / 100,
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>{symbol} Price History</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={420}>
          <LineChart data={chartData} margin={{ top: 8, right: 24, bottom: 8, left: 8 }}>
            {/* gradient for area fill */}
            <defs>
              <linearGradient id="priceArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CHART_COLORS.areaFrom} />
                <stop offset="100%" stopColor={CHART_COLORS.areaTo} />
              </linearGradient>
            </defs>

            <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" />
            <XAxis
              dataKey="timestamp"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(ts) => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              tick={{ fill: CHART_COLORS.axis }}
              stroke={CHART_COLORS.grid}
              axisLine={{ stroke: CHART_COLORS.grid } as any}
              tickLine={{ stroke: CHART_COLORS.grid } as any}
              tickCount={5}
            />
            <YAxis
              type="number"
              domain={yDomain as any}
              tick={{ fill: CHART_COLORS.axis }}
              stroke={CHART_COLORS.grid}
              axisLine={{ stroke: CHART_COLORS.grid } as any}
              tickLine={{ stroke: CHART_COLORS.grid } as any}
              tickFormatter={(v) => formatNumberShort(Number(v))}
              width={64}
              tickCount={6}
            />
            <Tooltip
              labelFormatter={(ts) => new Date(ts).toLocaleString()}
              contentStyle={{
                backgroundColor: CHART_COLORS.tooltipBg,
                border: `1px solid ${CHART_COLORS.tooltipBorder}`,
                borderRadius: "0.5rem",
                color: CHART_COLORS.label,
              }}
              formatter={(value: any) => [`$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 8 })}`, 'Price']}
            />
            {/* smooth area under the line for visual density */}
            <Area
              type="monotone"
              dataKey="price"
              stroke="transparent"
              fill="url(#priceArea)"
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="price"
              stroke={CHART_COLORS.line}
              strokeWidth={2.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export function PriceCharts() {
  const [selectedSymbol, setSelectedSymbol] = useState<string>(symbols[0])
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-xl font-semibold">Historical Charts</h2>
        <div className="w-40">
          <Select value={selectedSymbol} onValueChange={setSelectedSymbol}>
            <SelectTrigger>
              <SelectValue placeholder="Select symbol" />
            </SelectTrigger>
            <SelectContent>
              {symbols.map((s) => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Single, full-width chart for the selected symbol */}
      <div className="w-full">
        <PriceChart symbol={selectedSymbol} />
      </div>
    </div>
  )
}
