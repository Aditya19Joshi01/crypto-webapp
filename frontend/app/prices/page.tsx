import { AppSidebar } from "@/components/app-sidebar"
import { Header } from "@/components/header"
import { PriceCharts } from "@/components/price-charts"
import { PriceTable } from "@/components/price-table"
import { LiveTicker } from "@/components/live-ticker"

export default function PricesPage() {
  return (
    <div className="flex h-screen">
      <AppSidebar />
      <div className="flex flex-1 flex-col">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          <div className="mx-auto max-w-7xl space-y-6">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Price Analytics</h1>
              <p className="mt-2 text-muted-foreground">Historical price data and real-time updates</p>
            </div>
            <LiveTicker />
            <PriceCharts />
            <PriceTable />
          </div>
        </main>
      </div>
    </div>
  )
}
