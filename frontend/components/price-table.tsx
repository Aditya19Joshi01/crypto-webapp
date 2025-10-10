"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

const symbols = ["BTC", "ETH", "cUSD"]

async function fetchPriceHistory(symbol: string) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const response = await fetch(`${apiUrl}/prices/${symbol}`)
  if (!response.ok) throw new Error("Failed to fetch price history")
  return response.json()
}

export function PriceTable() {
  const [selectedSymbol, setSelectedSymbol] = useState("BTC")
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10

  const { data, isLoading } = useQuery({
    queryKey: ["priceHistory", selectedSymbol],
    queryFn: () => fetchPriceHistory(selectedSymbol),
  })

  const totalPages = Math.ceil((data?.length || 0) / itemsPerPage)
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
          <Select value={selectedSymbol} onValueChange={setSelectedSymbol}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {symbols.map((symbol) => (
                <SelectItem key={symbol} value={symbol}>
                  {symbol}
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
                    <TableCell className="font-semibold">{item.symbol || "-"}</TableCell>
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
                Showing {startIndex + 1} to {Math.min(startIndex + itemsPerPage, data?.length || 0)} of{" "}
                {data?.length || 0} entries
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
