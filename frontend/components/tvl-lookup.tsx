"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { Search } from "lucide-react"

async function fetchTvl(protocol: string) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const response = await fetch(`${apiUrl}/tvl/${protocol}`)
  if (!response.ok) throw new Error("Failed to fetch TVL")
  return response.json()
}

export function TvlLookup() {
  const [protocol, setProtocol] = useState("")
  const [searchProtocol, setSearchProtocol] = useState("")

  const { data, isLoading, error } = useQuery({
    queryKey: ["tvl", searchProtocol],
    queryFn: () => fetchTvl(searchProtocol),
    enabled: !!searchProtocol,
  })

  const handleSearch = () => {
    if (protocol.trim()) {
      setSearchProtocol(protocol.trim())
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Protocol Lookup</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Enter protocol name (e.g., uniswap, aave)"
              value={protocol}
              onChange={(e) => setProtocol(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
            <Button onClick={handleSearch} disabled={!protocol.trim()}>
              <Search className="mr-2 h-4 w-4" />
              Search
            </Button>
          </div>
        </CardContent>
      </Card>

      {isLoading && (
        <Card>
          <CardContent className="pt-6">
            <Skeleton className="h-24 w-full" />
          </CardContent>
        </Card>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>
            Failed to fetch TVL for {searchProtocol}. Please check the protocol name and try again.
          </AlertDescription>
        </Alert>
      )}

      {data && !isLoading && (
        <Card>
          <CardHeader>
            <CardTitle className="capitalize">{searchProtocol}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <p className="text-sm text-muted-foreground">Total Value Locked</p>
                <p className="text-4xl font-bold">
                  $
                  {data.tvl?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || "N/A"}
                </p>
              </div>
              {data.chain && (
                <div>
                  <p className="text-sm text-muted-foreground">Chain</p>
                  <p className="text-lg font-medium capitalize">{data.chain}</p>
                </div>
              )}
              {data.timestamp && (
                <div>
                  <p className="text-sm text-muted-foreground">Last Updated</p>
                  <p className="text-sm">{new Date(data.timestamp).toLocaleString()}</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
