import requests
import pandas as pd
import os
import time
from datetime import datetime, timedelta
from functools import lru_cache
from fastapi import FastAPI

app = FastAPI()

API_KEY = os.getenv("FMP_API_KEY")
COINGECKO_IDS = {"btc": "bitcoin", "eth": "ethereum"}  # Add more: e.g., "ada": "cardano"

cache = {}  # Simple in-memory cache

def get_date_30_days_ago():
    return (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

def make_request_with_retry(url, params=None, max_retries=3):
    for attempt in range(max_retries):
        r = requests.get(url, params=params)
        if r.status_code == 200:
            return r
        elif r.status_code == 429:
            wait_time = (2 ** attempt) + 1  # Backoff: 1s, 3s, 7s
            time.sleep(wait_time)
            continue
        else:
            break
    return r

@lru_cache(maxsize=128)
def fetch_crypto_data(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": 30}
    r = make_request_with_retry(url, params)
    if r.status_code != 200:
        raise ValueError(f"Failed to fetch crypto data: {r.status_code} - {r.text[:100]}")
    return pd.DataFrame(r.json()["prices"], columns=["timestamp", "Close"])["Close"].astype(float)

@app.get("/")
def root():
    return {"status": "✅ Trading Backend is running!"}

@app.get("/analyze")
def analyze(symbol: str):
    global cache
    try:
        original_symbol = symbol
        if "=" in symbol:
            symbol = symbol.split("=")[0]  # EURUSD=X -> EURUSD
        if not symbol.endswith("-USD") and symbol.upper().endswith("USD"):
            symbol = symbol[:-3] + "-USD"  # BTCUSD -> BTC-USD
        is_crypto = symbol.split("-")[0].lower() in COINGECKO_IDS if "-" in symbol else False

        # Check cache first (5-min TTL)
        cache_key = f"{symbol}_{int(time.time() // 300)}"
        if cache_key in cache:
            return {"symbol": original_symbol.upper(), **cache[cache_key]}

        if is_crypto:
            ticker = symbol.split("-")[0].lower()
            coin_id = COINGECKO_IDS[ticker]
            closes = fetch_crypto_data(coin_id)
            data = pd.DataFrame({"Close": closes})
        else:
            if not API_KEY:
                return {"symbol": original_symbol, "error": "FMP API key not set (check env vars)"}
            fmp_symbol = symbol.replace("-", "").upper()
            from_date = get_date_30_days_ago()
            to_date = datetime.now().strftime("%Y-%m-%d")
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{fmp_symbol}?from={from_date}&to={to_date}&apikey={API_KEY}"
            r = make_request_with_retry(url)
            json_data = r.json()
            if r.status_code != 200 or not json_data or "historical" not in json_data:
                return {"symbol": original_symbol, "error": f"No data for {fmp_symbol}: {r.status_code} - {r.text[:100]} (check symbol/API key/limits)"}
            data = pd.DataFrame(json_data["historical"])
            data.rename(columns={"close": "Close"}, inplace=True)
            if len(data) < 14:
                return {"symbol": original_symbol, "error": "Insufficient historical data (<14 periods)"}

        # RSI (14-period)
        delta = data["Close"].diff()
        gain = delta.clip(lower=0).rolling(window=14).mean()
        loss = (-delta.clip(upper=0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = round(rsi.iloc[-1], 2) if not pd.isna(rsi.iloc[-1]) else None

        # MACD (12/26/9)
        exp1 = data["Close"].ewm(span=12, adjust=False).mean()
        exp2 = data["Close"].ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_value = round((macd_line.iloc[-1] - signal.iloc[-1]), 4) if len(data) >= 26 else None

        trend = "📈 Bullish" if macd_value and macd_value > 0 else "📉 Bearish" if macd_value else "❓ Neutral"

        result = {"rsi": rsi_value, "macd": macd_value, "trend": trend}
        cache[cache_key] = result  # Cache for next 5 min

        return {"symbol": original_symbol.upper(), **result}

    except Exception as e:
        return {"symbol": original_symbol, "error": str(e)}
