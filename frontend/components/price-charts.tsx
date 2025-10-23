"use client"

import { useQuery } from "@tanstack/react-query"
import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area } from "recharts"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { getCoins, toUiTicker } from "@/lib/api"

const CHART_COLORS = {
  axis: "#A3A3A3",
  grid: "#2A2E39",
  line: "#F0B90B",
  areaFrom: "rgba(240, 185, 11, 0.24)",
  areaTo: "rgba(240, 185, 11, 0.04)",
  tooltipBg: "#0B0E11",
  tooltipBorder: "#2A2E39",
  label: "#E5E7EB",
}

function formatNumberShort(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 1e12) return `${(value / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${(value / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${(value / 1e6).toFixed(2)}M`
  if (abs >= 1e3) return `${(value / 1e3).toFixed(2)}K`
  return `${value}`
}

// fetch historical prices by backend symbol
async function fetchPriceHistoryByBackendSymbol(backendSymbol: string) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const response = await fetch(`${apiUrl}/prices/${backendSymbol}`)
  if (!response.ok) throw new Error("Failed to fetch price history")
  const json = await response.json()
  const prices = Array.isArray(json?.prices) ? json.prices : []
  return prices.map((p: any) => ({ price: Number(p.price), timestamp: p.timestamp }))
}

function PriceChart({ backendSymbol, display }: { backendSymbol: string; display: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["priceHistory", backendSymbol],
    queryFn: () => fetchPriceHistoryByBackendSymbol(backendSymbol),
    enabled: !!backendSymbol,
    refetchInterval: 5000,
    keepPreviousData: true,
  })

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{display} Price History</CardTitle>
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
          <CardTitle>{display} Price History</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>Failed to load price history for {display}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    )
  }

  // Prepare chart data: ensure chronological ascending order for smooth animation
  const chartData = data
    .map((item: any) => {
      if (!item || item.price == null || !item.timestamp) return null
      return {
        timestamp: new Date(item.timestamp).getTime(),
        price: Number(item.price),
      }
    })
    .filter(Boolean)
    .sort((a: any, b: any) => a.timestamp - b.timestamp)

  const prices = chartData.map((item: any) => item.price)
  const hasAny = prices.length > 0
  const minPrice = hasAny ? Math.min(...prices) : 0
  const maxPrice = hasAny ? Math.max(...prices) : 0
  const spread = Math.max(0.01, maxPrice - minPrice)
  const yDomain = [
    Math.floor((minPrice - spread * 0.05) * 100) / 100,
    Math.ceil((maxPrice + spread * 0.05) * 100) / 100,
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>{display} Price History</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={420}>
          <LineChart data={chartData} margin={{ top: 8, right: 24, bottom: 8, left: 8 }}>
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
              isAnimationActive={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export function PriceCharts() {
  const { data: coins, isLoading } = useQuery({ queryKey: ["coins"], queryFn: getCoins, refetchInterval: 30000, refetchOnWindowFocus: true })
  const coinList = coins || []
  const [selectedBackendSymbol, setSelectedBackendSymbol] = useState<string>("")

  // Set default when coins finish loading
  useEffect(() => {
    if (!isLoading && coinList.length > 0 && !selectedBackendSymbol) {
      setSelectedBackendSymbol(coinList[0].symbol)
    }
  }, [coinList, isLoading, selectedBackendSymbol])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-xl font-semibold">Historical Charts</h2>
        <div className="w-40">
          <Select value={selectedBackendSymbol} onValueChange={setSelectedBackendSymbol}>
            <SelectTrigger>
              <SelectValue placeholder="Select symbol" />
            </SelectTrigger>
            <SelectContent>
              {coinList.map((c: any) => (
                <SelectItem key={c.symbol} value={c.symbol}>{toUiTicker(c.symbol, c.name)}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="w-full">
        {selectedBackendSymbol ? (
          <PriceChart backendSymbol={selectedBackendSymbol} display={toUiTicker(selectedBackendSymbol)} />
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Select a symbol to view the chart</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">Waiting for symbols from backend...</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
