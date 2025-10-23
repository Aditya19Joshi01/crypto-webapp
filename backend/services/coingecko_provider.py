import logging
from typing import Optional
import httpx
from backend.services.base_provider import PriceProvider

logger = logging.getLogger("backend.services.coingecko")

COINGECKO_API_URL = "https://api.coingecko.com/api/v3/simple/price"


class CoinGeckoProvider(PriceProvider):
    """
    Fetches cryptocurrency prices from CoinGecko API.
    Supports any coin available on CoinGecko.
    """

    def __init__(self, symbol: str, coingecko_id: str, display_name: str):
        """
        Args:
            symbol: Internal symbol (e.g., 'btc')
            coingecko_id: CoinGecko API ID (e.g., 'bitcoin')
            display_name: Human-readable name (e.g., 'Bitcoin')
        """
        super().__init__(symbol)
        self.coingecko_id = coingecko_id
        self.display_name = display_name

    async def fetch_price(self, client: httpx.AsyncClient) -> Optional[float]:
        """Fetch Price from CoinGecko API"""
        params = {
            "ids": self.coingecko_id,
            "vs_currencies" : "usd"
        }

        try:
            response = await client.get(
                COINGECKO_API_URL,
                params=params,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

            if self.coingecko_id in data and "usd" in data[self.coingecko_id]:
                price = float(data[self.coingecko_id]["usd"])
                logger.info(f"Fetched {self.symbol} price: ${price:,.2f}")
                return price

            logger.warning(f"No price data for {self.symbol} in CoinGeko response")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch {self.symbol} from CoinGecko: {e}")
            return None

    def get_display_name(self) -> str:
        return self.display_name

    def get_provider_name(self) -> str:
        return "CoinGecko"
