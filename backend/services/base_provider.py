from abc import ABC, abstractmethod
from typing import Optional
import httpx


class PriceProvider(ABC):
    """
    Abstract base class for all price providers.
    Any new provider must implement these methods.
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol
    
    @abstractmethod
    async def fetch_price(self, client: httpx.AsyncClient) -> Optional[float]:
        """
        Fetch the current price for this symbol.
        
        Args:
            client: Shared HTTP client for making requests
            
        Returns:
            Price as float, or None if fetch failed
        """
        pass
    
    @abstractmethod
    def get_display_name(self) -> str:
        """Return human-readable name (e.g., 'Bitcoin', 'Ethereum')"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return data source name (e.g., 'CoinGecko', 'Celo Blockchain')"""
        pass