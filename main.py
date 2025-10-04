import requests
import pandas as pd
import os
from datetime import datetime, timedelta
from fastapi import FastAPI

app = FastAPI()

API_KEY = os.getenv("FMP_API_KEY")  # Required; set in Render dashboard

COINGECKO_IDS = {"btc": "bitcoin", "eth": "ethereum"}  # Expand as needed

def get_date_30_days_ago():
    return (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

@app.get("/")
def root():
    return {"status": "✅ Trading Backend is running!"}

@app.get("/analyze")
def analyze(symbol: str):
    try:
        # Normalize symbol
        original_symbol = symbol
        if "=" in symbol:
            symbol = symbol.split("=")[0]  # EURUSD=X -> EURUSD
        if not symbol.endswith("-USD") and symbol.upper().endswith("USD"):
            symbol = symbol[:-3] + "-USD"  # BTCUSD -> BTC-USD
        is_crypto = symbol.split("-")[0].lower() in COINGECKO_IDS if "-" in symbol else False

        if is_crypto:
            # CoinGecko for crypto
            ticker = symbol.split("-")[0].lower()
            coin_id = COINGECKO_IDS[ticker]
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {"vs_currency": "usd", "days": 30}
            r = requests.get(url, params=params)
            if r.status_code != 200:
                return {"symbol": original_symbol, "error": f"Failed to fetch crypto data: {r.status_code} - {r.text[:100]}"}
            data = pd.DataFrame(r.json()["prices"], columns=["timestamp", "Close"])
            data["Close"] = data["Close"].astype(float)
        else:
            # FMP for stocks/forex (requires key)
            if not API_KEY:
                return {"symbol": original_symbol, "error": "FMP API key not set (check env vars)"}
            fmp_symbol = symbol.replace("-", "").upper()  # BTC-USD -> BTCUSD, but for forex/stocks it's fine
            from_date = get_date_30_days_ago()
            to_date = datetime.now().strftime("%Y-%m-%d")
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{fmp_symbol}?from={from_date}&to={to_date}&apikey={API_KEY}"
            r = requests.get(url)
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
        rsi_value = round(rsi.iloc[-1], 2)

        # MACD (12/26/9)
        exp1 = data["Close"].ewm(span=12, adjust=False).mean()
        exp2 = data["Close"].ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_value = round(macd_line.iloc[-1] - signal.iloc[-1], 4)

        trend = "📈 Bullish" if macd_value > 0 else "📉 Bearish"

        return {
            "symbol": original_symbol.upper(),
            "rsi": rsi_value,
            "macd": macd_value,
            "trend": trend
        }

    except Exception as e:
        return {"symbol": original_symbol, "error": str(e)}
