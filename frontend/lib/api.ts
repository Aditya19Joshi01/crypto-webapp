// filepath: c:\Users\ajhas\Desktop\b2c2-assignment\crypto-dashboard\frontend\lib\api.ts
export async function getCoins() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const res = await fetch(`${apiUrl}/coins`)
  if (!res.ok) throw new Error("Failed to fetch coins list")
  const json = await res.json()
  return Array.isArray(json?.coins) ? json.coins : []
}

export async function getMode() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  const res = await fetch(`${apiUrl}/mode`)
  if (!res.ok) throw new Error("Failed to fetch mode")
  const json = await res.json()
  return json
}

// Create a short UI ticker from a backend symbol or display name
export function toUiTicker(backendSymbol: string, displayName?: string) {
  // Known explicit mappings (keep this small)
  const key = backendSymbol?.toLowerCase?.() || ""
  if (key === "bitcoin" || (displayName || "").toLowerCase().includes("bitcoin")) return "BTC"
  if (key === "ethereum" || (displayName || "").toLowerCase().includes("ethereum")) return "ETH"
  if (key === "cusd" || (displayName || "").toLowerCase().includes("celo dollar") || (displayName || "").toLowerCase().includes("cusd")) return "cUSD"
  if (key === "solana" || (displayName || "").toLowerCase().includes("solana")) return "SOL"
  if (key === "cardano" || (displayName || "").toLowerCase().includes("cardano")) return "ADA"
  if (key === "binance" || (displayName || "").toLowerCase().includes("binance")) return "BNB"

  // If displayName exists, try to create a compact label from it:
  if (displayName && typeof displayName === "string") {
    // common pattern: single-word name -> uppercase (e.g., "Tether" -> "TETHER" trimmed to 6)
    const name = displayName.trim()
    if (!name.includes(" ") && name.length <= 6) return name.toUpperCase()
    // multi-word: take initials (e.g., "Celo Dollar" -> "CD") up to 4 chars
    const initials = name.split(/\s+/).map((w) => w[0]).join("").toUpperCase()
    if (initials.length >= 2 && initials.length <= 4) return initials
    // fallback: take first up to 6 chars of the display name (no spaces)
    const compact = name.replace(/\s+/g, "").toUpperCase()
    return compact.length > 6 ? compact.slice(0, 6) : compact
  }

  // Final fallback: uppercase backend symbol (trim if long)
  const up = backendSymbol ? backendSymbol.toUpperCase() : "UNKNOWN"
  return up.length > 6 ? up.slice(0, 6) : up
}
