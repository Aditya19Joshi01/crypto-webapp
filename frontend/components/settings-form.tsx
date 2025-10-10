"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { useToast } from "@/hooks/use-toast"

async function fetchMode() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const response = await fetch(`${apiUrl}/mode`)
  if (!response.ok) throw new Error("Failed to fetch mode")
  const data = await response.json()
  // Normalize backend boolean -> frontend string
  return { mode: data.live_mode ? "live" : "static", ...data }
}

async function updateMode(live: boolean) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const response = await fetch(`${apiUrl}/mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ live }), // backend expects this
  })
  if (!response.ok) throw new Error("Failed to update mode")
  const data = await response.json()
  // Normalize backend boolean -> frontend string
  return { mode: data.live_mode ? "live" : "static", ...data }
}


export function SettingsForm() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [pollInterval, setPollInterval] = useState("60")
  const [cacheRetention, setCacheRetention] = useState("300")

  const { data: modeData, isLoading } = useQuery({
    queryKey: ["mode"],
    queryFn: fetchMode,
  })

  const modeMutation = useMutation({
    mutationFn: updateMode,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mode"] })
      toast({
        title: "Success",
        description: "Mode updated successfully",
      })
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to update mode",
        variant: "destructive",
      })
    },
  })

  const handleModeToggle = (checked: boolean) => {
    modeMutation.mutate(checked) // directly pass boolean
  }


  if (isLoading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    )
  }

  const isLiveMode = modeData?.mode === "live"

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>API Mode</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Live Mode</Label>
              <p className="text-sm text-muted-foreground">Enable real-time data fetching from external APIs</p>
            </div>
            <Switch checked={isLiveMode} onCheckedChange={handleModeToggle} disabled={modeMutation.isPending} />
          </div>
          <Alert>
            <AlertDescription>
              Current mode: <strong>{modeData?.mode || "unknown"}</strong>
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Data Fetching Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="poll-interval">Poll Interval (seconds)</Label>
            <Input
              id="poll-interval"
              type="number"
              value={pollInterval}
              onChange={(e) => setPollInterval(e.target.value)}
              placeholder="60"
            />
            <p className="text-sm text-muted-foreground">How often to fetch new data from the API</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="cache-retention">Cache Retention (seconds)</Label>
            <Input
              id="cache-retention"
              type="number"
              value={cacheRetention}
              onChange={(e) => setCacheRetention(e.target.value)}
              placeholder="300"
            />
            <p className="text-sm text-muted-foreground">How long to keep cached data before refetching</p>
          </div>

          <Button className="w-full">Save Configuration</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API Connection</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label>Backend URL</Label>
            <Input value={process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"} disabled />
            <p className="text-sm text-muted-foreground">Set via NEXT_PUBLIC_API_URL environment variable</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
