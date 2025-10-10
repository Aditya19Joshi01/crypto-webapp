import { AppSidebar } from "@/components/app-sidebar"
import { Header } from "@/components/header"
import { PriceSummaryCards } from "@/components/price-summary-cards"

export default function HomePage() {
  return (
    <div className="flex h-screen">
      <AppSidebar />
      <div className="flex flex-1 flex-col">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          <div className="mx-auto max-w-7xl space-y-6">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-balance">Welcome to Crypto Dashboard</h1>
              <p className="mt-2 text-muted-foreground">Track real-time cryptocurrency prices and analytics</p>
            </div>
            <PriceSummaryCards />
          </div>
        </main>
      </div>
    </div>
  )
}
