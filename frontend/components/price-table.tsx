"use client"

import { useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { getCoins, toUiTicker } from "@/lib/api"

function toBackendSymbolFromUi(symbol: string): string {
  // if caller passes a backend symbol already, just return it
  return symbol
}

// Normalize the backend historical response into an array the component expects
async function fetchPriceHistory(backendSymbol: string) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const response = await fetch(`${apiUrl}/prices/${backendSymbol}`)
  if (!response.ok) throw new Error("Failed to fetch price history")
  const json = await response.json()

  // backend returns { symbol, count, prices: [{ price, timestamp }, ...] }
  const prices = Array.isArray(json?.prices) ? json.prices : []

  // Map to include a symbol and optional volume field so the table can render
  return prices.map((p: any) => ({
    symbol: backendSymbol,
    price: p.price,
    timestamp: p.timestamp,
    volume: p.volume ?? null,
  }))
}

export function PriceTable() {
  const { data: coins, isLoading: coinsLoading } = useQuery({ queryKey: ["coins"], queryFn: getCoins, refetchInterval: 30000, refetchOnWindowFocus: true })
  const coinList = coins || []

  const [selectedBackendSymbol, setSelectedBackendSymbol] = useState<string>("")
  useEffect(() => {
    if (!coinsLoading && coinList.length > 0) {
      setSelectedBackendSymbol(coinList[0].symbol)
    }
  }, [coinList, coinsLoading])
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10

  // Keep the history query keyed by backend symbol
  const { data, isLoading } = useQuery({
    queryKey: ["priceHistory", selectedBackendSymbol],
    enabled: !!selectedBackendSymbol,
    queryFn: () => fetchPriceHistory(selectedBackendSymbol),
  })

  const totalPages = Math.max(1, Math.ceil((data?.length || 0) / itemsPerPage))
  const startIndex = (currentPage - 1) * itemsPerPage
  const paginatedData =
    data
      ?.filter((item: any) => item && item.price != null && item.timestamp)
      .slice(startIndex, startIndex + itemsPerPage) || []

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Price History Table</CardTitle>
          <Select value={selectedBackendSymbol} onValueChange={(v) => { setSelectedBackendSymbol(v); setCurrentPage(1); }}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {coinList.map((coin: any) => (
                <SelectItem key={coin.symbol} value={coin.symbol}>
                  {toUiTicker(coin.symbol, coin.name)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Symbol</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="text-right">Volume</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedData.map((item: any, index: number) => (
                  <TableRow key={index}>
                    <TableCell className="font-mono text-sm">
                      {item.timestamp ? new Date(item.timestamp).toLocaleString() : "-"}
                    </TableCell>
                    <TableCell className="font-semibold">{toUiTicker(item.symbol)}</TableCell>
                    <TableCell className="text-right font-mono">
                      {item.price != null
                        ? Number(item.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                        : "N/A"}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {item.volume != null ? Number(item.volume).toLocaleString() : "N/A"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Showing {startIndex + 1} to {Math.min(startIndex + itemsPerPage, data?.length || 0)} of {data?.length || 0} entries
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
