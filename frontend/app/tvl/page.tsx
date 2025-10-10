import { AppSidebar } from "@/components/app-sidebar"
import { Header } from "@/components/header"
import { TvlLookup } from "@/components/tvl-lookup"

export default function TvlPage() {
  return (
    <div className="flex h-screen">
      <AppSidebar />
      <div className="flex flex-1 flex-col">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          <div className="mx-auto max-w-3xl space-y-6">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Total Value Locked</h1>
              <p className="mt-2 text-muted-foreground">Query TVL data for DeFi protocols</p>
            </div>
            <TvlLookup />
          </div>
        </main>
      </div>
    </div>
  )
}
