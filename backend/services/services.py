import httpx
from typing import Optional
from datetime import datetime
import logging
import os
from web3 import Web3
from web3.middleware import geth_poa_middleware
import asyncio

COINGECKO_SIMPLE_URL = "https://api.coingecko.com/api/v3/simple/price"
DEFILLAMA_TVL_URL = "https://api.llama.fi/tvl/"

# Celo / Mento configuration (override via env if needed)
CELO_RPC_URL = os.getenv("CELO_RPC_URL", "https://forno.celo.org")
# Celo Registry well-known address on mainnet
CELO_REGISTRY_ADDRESS = os.getenv(
    "CELO_REGISTRY_ADDRESS", "0x000000000000000000000000000000000000ce10"
)
CUSD_ADDRESS = os.getenv("CUSD_ADDRESS", "0x765DE816845861e75A25fCA122bb6898B8B1282a")

logger = logging.getLogger("backend.services")


async def fetch_coingecko_price(
    client: httpx.AsyncClient, coin_id: str
) -> Optional[float]:
    params = {"ids": coin_id, "vs_currencies": "usd"}
    try:
        resp = await client.get(COINGECKO_SIMPLE_URL, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        if coin_id in data and "usd" in data[coin_id]:
            logger.debug(f"CoinGecko {coin_id} response: {data[coin_id]}")
            return float(data[coin_id]["usd"])
    except Exception:
        logger.exception(f"CoinGecko request failed for {coin_id}")
        return None
    return None


async def fetch_defillama_tvl(client: httpx.AsyncClient, protocol: str):
    try:
        resp = await client.get(DEFILLAMA_TVL_URL + protocol, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        logger.debug(
            f"DeFiLlama {protocol} TVL fetched with {len(data) if isinstance(data, list) else 'obj'} entries"
        )
        return data
    except Exception:
        logger.exception(f"DeFiLlama request failed for protocol={protocol}")
        return None


def _get_web3() -> Web3:
    w3 = Web3(Web3.HTTPProvider(CELO_RPC_URL, request_kwargs={"timeout": 10}))
    try:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except Exception:
        pass
    return w3


def _fetch_cusd_price_blocking() -> Optional[float]:
    w3 = _get_web3()
    if not w3.is_connected():
        logger.error("Web3 not connected to Celo RPC")
        return None
    try:
        # Resolve SortedOracles address from the Registry contract to avoid hardcoding
        registry = w3.eth.contract(
            address=Web3.to_checksum_address(CELO_REGISTRY_ADDRESS),
            abi=[
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "identifier",
                            "type": "string",
                        }
                    ],
                    "name": "getAddressForString",
                    "outputs": [
                        {"internalType": "address", "name": "addr", "type": "address"}
                    ],
                    "stateMutability": "view",
                    "type": "function",
                }
            ],
        )
        sorted_oracles_addr = registry.functions.getAddressForString(
            "SortedOracles"
        ).call()
        if int(sorted_oracles_addr, 16) == 0:
            logger.error("Registry returned zero address for SortedOracles")
            return None
        sorted_oracles = w3.eth.contract(
            address=sorted_oracles_addr,
            abi=[
                {
                    "inputs": [
                        {"internalType": "address", "name": "token", "type": "address"}
                    ],
                    "name": "medianRate",
                    "outputs": [
                        {
                            "internalType": "uint256",
                            "name": "numerator",
                            "type": "uint256",
                        },
                        {
                            "internalType": "uint256",
                            "name": "denominator",
                            "type": "uint256",
                        },
                    ],
                    "stateMutability": "view",
                    "type": "function",
                }
            ],
        )
        token = Web3.to_checksum_address(CUSD_ADDRESS)
        num, den = sorted_oracles.functions.medianRate(token).call()
        if den == 0:
            logger.error("Oracle returned denominator 0 for cUSD/USD")
            return None
        price = float(num) / float(den)
        return price
    except Exception:
        logger.exception("Failed to fetch cUSD price from SortedOracles")
        return None


async def fetch_cusd_price() -> Optional[float]:
    logger.debug("Fetching cUSD price from Celo blockchain")
    return await asyncio.to_thread(_fetch_cusd_price_blocking)
