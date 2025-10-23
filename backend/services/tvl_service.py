import logging
import asyncio
from typing import Any, Dict

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)


async def fetch_tvl(protocol: str, client: httpx.AsyncClient, attempts: int = 3, timeout: float = 10.0) -> Dict[str, Any]:
    """
    Fetch TVL for a given protocol from the DeFiLlama API.

    Behaviour mirrors the previous inline implementation in `app.py`:
    - retries up to `attempts` times on errors
    - treats 404 as protocol not found and raises HTTPException(404)
    - returns a normalized dict for numeric/list/dict/string responses
    - on repeated failures raises HTTPException(502)
    """
    url = f"https://api.llama.fi/tvl/{protocol}"
    attempt = 0
    last_exc = None

    while attempt < attempts:
        try:
            if attempt > 0:
                logger.debug(f"TVL retry attempt {attempt} for {protocol}")

            resp = await client.get(url, timeout=timeout)
            if resp.status_code == 404:
                logger.error(f"TVL protocol not found: {protocol}")
                raise HTTPException(status_code=404, detail="Protocol not found")

            resp.raise_for_status()

            # Try to parse JSON first
            try:
                data = resp.json()
            except Exception:
                # Not JSON — try to parse as a float/scalar from text
                text = resp.text.strip()
                try:
                    val = float(text)
                    logger.debug(
                        f"TVL scalar response parsed as float for {protocol}: {val}"
                    )
                    return {"tvl": val}
                except Exception:
                    logger.debug(
                        f"TVL non-JSON/non-numeric response for {protocol}: {text}"
                    )
                    return {"tvl_raw": text}

            # If JSON parsed successfully, normalize into an object the frontend can consume
            if isinstance(data, (int, float)):
                return {"tvl": float(data)}
            if isinstance(data, str):
                try:
                    return {"tvl": float(data)}
                except Exception:
                    return {"tvl_raw": data}
            if isinstance(data, list):
                return {"items": data}
            if isinstance(data, dict):
                if "tvl" in data:
                    try:
                        data["tvl"] = (
                            float(data["tvl"]) if data["tvl"] is not None else None
                        )
                    except Exception:
                        # leave as-is if conversion fails
                        pass
                return data

        except httpx.HTTPStatusError as e:
            last_exc = e
            attempt += 1
            if attempt >= attempts:
                logger.error(f"TVL fetch failed for {protocol}: {e}")
                raise HTTPException(
                    status_code=502, detail="Upstream TVL service error"
                )
            await asyncio.sleep(2 ** (attempt - 1))
        except Exception as e:
            last_exc = e
            attempt += 1
            if attempt >= attempts:
                logger.error(f"TVL fetch unreachable for {protocol}: {e}")
                raise HTTPException(
                    status_code=502, detail="TVL service unreachable"
                )
            await asyncio.sleep(2 ** (attempt - 1))

    # If we fall out of loop unexpectedly, raise a generic error
    logger.error(f"TVL fetch exhausted retries for {protocol}: {last_exc}")
    raise HTTPException(status_code=502, detail="TVL fetch failed")

