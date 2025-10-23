import logging
from typing import Optional
import httpx
from backend.services.base_provider import PriceProvider

logger = logging.getLogger("backend.services.binance")

BINANCE_API_URL = "https://api.binance.com/api/v3/ticker/price"


class BinanceProvider(PriceProvider):
    """
    Fetches cryptocurrency prices from Binance API.
    """

    def __init__(self, symbol: str, binance_symbol: str, display_name: str):
        """
        Args:
            symbol: Internal symbol (e.g., 'btc')
            binance_symbol: Binance trading pair (e.g., 'BTCUSDT')
            display_name: Human-readable name (e.g., 'Bitcoin')
        """
        super().__init__(symbol)
        self.binance_symbol = binance_symbol
        self.display_name = display_name

    async def fetch_price(self, client: httpx.AsyncClient) -> Optional[float]:
        """Fetch price from Binance API"""
        params = {"symbol": self.binance_symbol}

        try:
            resp = await client.get(
                BINANCE_API_URL,
                params=params,
                timeout=10.0
            )
            resp.raise_for_status()
            data = resp.json()

            if "price" in data:
                price = float(data["price"])
                logger.info(f"Fetched {self.symbol} price: ${price:,.2f}")
                return price

            logger.warning(f"No price in Binance response for {self.symbol}")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch {self.symbol} from Binance: {e}")
            return None

    def get_display_name(self) -> str:
        return self.display_name

    def get_provider_name(self) -> str:
        return "Binance"