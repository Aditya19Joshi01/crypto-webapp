import logging
import asyncio
from typing import Optional
import httpx
from web3 import Web3
from web3.middleware import geth_poa_middleware
from backend.services.base_provider import PriceProvider

logger = logging.getLogger("backend.services.celo")

CELO_RPC_URL = "https://forno.celo.org"
CELO_REGISTRY_ADDRESS = "0x000000000000000000000000000000000000ce10"


class CeloStablecoinProvider(PriceProvider):
    """
    Fetches stablecoin prices from Celo blockchain oracles.
    Uses on-chain SortedOracles contract.
    """

    def __init__(self, symbol: str, token_address: str, display_name: str):
        """
        Args:
            symbol: Internal symbol (e.g., 'cusd')
            token_address: Celo token contract address
            display_name: Human-readable name (e.g., 'Celo Dollar')
        """
        super().__init__(symbol)
        self.token_address = token_address
        self.display_name = display_name

    async def fetch_price(self, client: httpx.AsyncClient) -> Optional[float]:
        """Fetch price from Celo blockchain (runs in thread pool)"""
        return await asyncio.to_thread(self._fetch_price_blocking)

    def _fetch_price_blocking(self) -> Optional[float]:
        """Blocking Web3 call (run in thread pool)"""
        try:
            w3 = Web3(Web3.HTTPProvider(CELO_RPC_URL, request_kwargs={"timeout": 10}))
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)

            if not w3.is_connected():
                logger.error(f"Cannot connect to Celo RPC for {self.symbol}")
                return None

            # Get Registry contract
            registry = w3.eth.contract(
                address=Web3.to_checksum_address(CELO_REGISTRY_ADDRESS),
                abi=[{
                    "inputs": [{"name": "identifier", "type": "string"}],
                    "name": "getAddressForString",
                    "outputs": [{"name": "addr", "type": "address"}],
                    "stateMutability": "view",
                    "type": "function"
                }]
            )

            # Get SortedOracles address
            sorted_oracles_addr = registry.functions.getAddressForString("SortedOracles").call()
            if int(sorted_oracles_addr, 16) == 0:
                logger.error(f"Registry returned zero address for {self.symbol}")
                return None

            # Get SortedOracles contract
            sorted_oracles = w3.eth.contract(
                address=sorted_oracles_addr,
                abi=[{
                    "inputs": [{"name": "token", "type": "address"}],
                    "name": "medianRate",
                    "outputs": [
                        {"name": "numerator", "type": "uint256"},
                        {"name": "denominator", "type": "uint256"}
                    ],
                    "stateMutability": "view",
                    "type": "function"
                }]
            )

            # Get median rate
            token = Web3.to_checksum_address(self.token_address)
            num, den = sorted_oracles.functions.medianRate(token).call()

            if den == 0:
                logger.error(f"Oracle returned zero denominator for {self.symbol}")
                return None

            price = float(num) / float(den)
            logger.info(f"Fetched {self.symbol} price: ${price:.4f}")
            return price

        except Exception as e:
            logger.error(f"Failed to fetch {self.symbol} from Celo: {e}")
            return None

    def get_display_name(self) -> str:
        return self.display_name

    def get_provider_name(self) -> str:
        return "Celo Blockchain"