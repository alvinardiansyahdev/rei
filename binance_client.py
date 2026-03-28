import hmac
import hashlib
import time
import datetime
import aiohttp
from config import BINANCE_API_KEY, BINANCE_API_SECRET

FAPI_URL = "https://fapi.binance.com"
SAPI_URL = "https://api.binance.com"


def _sign(params: dict) -> str:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return hmac.new(
        BINANCE_API_SECRET.encode(), query.encode(), hashlib.sha256
    ).hexdigest()


async def _get(session: aiohttp.ClientSession, base: str, path: str, params: dict = None) -> any:
    params = params or {}
    params["timestamp"] = int(time.time() * 1000)
    params["signature"] = _sign(params)
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    async with session.get(base + path, params=params, headers=headers) as resp:
        data = await resp.json()
        if isinstance(data, dict) and data.get("code") and data.get("code") != 200:
            raise Exception(f"Binance API error {data.get('code')}: {data.get('msg')}")
        return data


async def get_positions(session: aiohttp.ClientSession) -> list:
    """Ambil semua posisi futures aktif (copy trading posisi masuk di sini)."""
    data = await _get(session, FAPI_URL, "/fapi/v3/positionRisk")
    if not isinstance(data, list):
        return []
    return [p for p in data if float(p.get("positionAmt", 0)) != 0]


async def get_wallet_balance(session: aiohttp.ClientSession) -> list:
    """Ambil semua wallet balance dalam USDT."""
    data = await _get(session, SAPI_URL, "/sapi/v1/asset/wallet/balance", {"quoteAsset": "USDT"})
    return data if isinstance(data, list) else []


async def get_copy_trading_balance(session: aiohttp.ClientSession) -> float:
    """Ambil khusus balance wallet Copy Trading dalam USDT."""
    wallets = await get_wallet_balance(session)
    for w in wallets:
        if "copy" in w.get("walletName", "").lower():
            return float(w.get("balance", 0))
    return 0.0
