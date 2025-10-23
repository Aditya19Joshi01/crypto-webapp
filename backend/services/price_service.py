import logging
from typing import Dict, List, Optional
import httpx
from backend.services.base_provider import PriceProvider
from backend.services.coingecko_provider import CoinGeckoProvider
from backend.services.celo_provider import CeloStablecoinProvider
from backend.services.binance_provider import BinanceProvider

logger = logging.getLogger("backend.services.price_service")


class PriceService:
    """
    Central registry for all cryptocurrency price providers.
    Manages provider lifecycle and provides unified interface.
    """

    def __init__(self):
        self.providers: Dict[str, PriceProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """
        Register all supported cryptocurrencies and their providers.
        This is the ONLY place you need to add new coins!
        """
        # Bitcoin - CoinGecko
        self.register_provider(
            CoinGeckoProvider(
                symbol="bitcoin",
                coingecko_id="bitcoin",
                display_name="Bitcoin"
            )
        )

        # Ethereum - CoinGecko
        self.register_provider(
            CoinGeckoProvider(
                symbol="ethereum",
                coingecko_id="ethereum",
                display_name="Ethereum"
            )
        )

        # Solana - CoinGecko (NEW COIN - Just add here!)
        self.register_provider(
            CoinGeckoProvider(
                symbol="solana",
                coingecko_id="solana",
                display_name="Solana"
            )
        )

        # Cardano - CoinGecko (NEW COIN - Just add here!)
        self.register_provider(
            CoinGeckoProvider(
                symbol="cardano",
                coingecko_id="cardano",
                display_name="Cardano"
            )
        )

        # Celo Dollar - Celo Blockchain
        self.register_provider(
            CeloStablecoinProvider(
                symbol="cusd",
                token_address="0x765DE816845861e75A25fCA122bb6898B8B1282a",
                display_name="Celo Dollar"
            )
        )

        # Bitcoin via Binance (alternative provider)
        # self.register_provider(
        #     BinanceProvider(
        #         symbol="bitcoin-binance",
        #         binance_symbol="BTCUSDT",
        #         display_name="Bitcoin (Binance)"
        #     )
        # )

        logger.info(f"Initialized {len(self.providers)} price providers")

    def register_provider(self, provider: PriceProvider):
        """Register a new price provider"""
        self.providers[provider.symbol] = provider
        logger.info(
            f"Registered {provider.symbol}: "
            f"{provider.get_display_name()} via {provider.get_provider_name()}"
        )

    def get_provider(self, symbol: str) -> Optional[PriceProvider]:
        """Get provider for a specific symbol"""
        return self.providers.get(symbol)

    def get_all_symbols(self) -> List[str]:
        """Get list of all supported symbols"""
        return list(self.providers.keys())

    def get_all_providers(self) -> List[PriceProvider]:
        """Get list of all providers"""
        return list(self.providers.values())

    async def fetch_price(
            self,
            symbol: str,
            client: httpx.AsyncClient
    ) -> Optional[float]:
        """
        Fetch price for a specific symbol.
        Automatically uses the correct provider.
        """
        provider = self.get_provider(symbol)
        if not provider:
            logger.error(f"No provider found for symbol: {symbol}")
            return None

        return await provider.fetch_price(client)

    async def fetch_all_prices(
            self,
            client: httpx.AsyncClient
    ) -> Dict[str, Optional[float]]:
        """
        Fetch prices for ALL registered symbols concurrently.
        Returns dict of {symbol: price}
        """
        import asyncio

        tasks = []
        symbols = []

        for symbol, provider in self.providers.items():
            tasks.append(provider.fetch_price(client))
            symbols.append(symbol)

        # Execute all fetches concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dict
        prices = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Exception fetching {symbol}: {result}")
                prices[symbol] = None
            else:
                prices[symbol] = result

        return prices


# Singleton instance
price_service = PriceService()