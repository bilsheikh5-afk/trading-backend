import requests
import pandas as pd
import os
from fastapi import FastAPI

app = FastAPI()

API_KEY = os.getenv("FMP_API_KEY")  # Set this in Render env vars

COINGECKO_IDS = {"btc": "bitcoin", "eth": "ethereum"}  # Add more as needed

@app.get("/")
def root():
    return {"status": "✅ Trading Backend is running!"}

@app.get("/analyze")
def analyze(symbol: str):
    try:
        # Normalize symbol (handle BTCUSD -> BTC-USD for consistency)
        if not symbol.endswith("-USD") and symbol.upper().endswith("USD"):
            symbol = symbol[:-3] + "-USD"
        
        is_crypto = symbol.upper() in ["BTC-USD", "ETH-USD"]  # Extend list as needed
        
        if is_crypto:
            # Use CoinGecko for crypto (more reliable, free)
            ticker = symbol.split("-")[0].lower()
            if ticker in COINGECKO_IDS:
                coin_id = COINGECKO_IDS[ticker]
                url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
                params = {"vs_currency": "usd", "days": 30}
                r = requests.get(url, params=params)
                if r.status_code != 200:
                    return {"symbol": symbol, "error": f"Failed to fetch crypto data: {r.text}"}
                data = pd.DataFrame(r.json()["prices"], columns=["timestamp", "Close"])
                data["Close"] = data["Close"].astype(float)
            else:
                raise ValueError(f"Unsupported crypto: {ticker}")
        else:
            # Use FMP for stocks (or extend for other cryptos)
            # For crypto like BTCUSD, you'd detect and use crypto endpoint below
            if symbol.upper().endswith("USD") and len(symbol) <= 7:  # e.g., BTCUSD
                # FMP crypto historical endpoint
                crypto_symbol = symbol.replace("-", "").upper()  # BTC-USD -> BTCUSD
                url = f"https://financialmodelingprep.com/stable/historical-price-eod/full"
                params = {"symbol": crypto_symbol, "apikey": API_KEY}
                r = requests.get(url, params=params)
                json_data = r.json()
                if not json_data or "historical" not in json_data[0]:  # FMP crypto wraps in list
                    return {"symbol": symbol, "error": "No data available for this crypto symbol (check API key/limits)"}
                data = pd.DataFrame(json_data[0]["historical"])
            else:
                # Stock endpoint
                url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol.upper()}?timeseries=30&apikey={API_KEY}"
                r = requests.get(url)
                json_data = r.json()
                if "historical" not in json_data:
                    return {"symbol": symbol, "error": "No data available for this symbol (check API key/limits)"}
                data = pd.DataFrame(json_data["historical"])
            
            data.rename(columns={"close": "Close"}, inplace=True)

        # RSI Calculation (drop NaNs implicitly via iloc)
        delta = data["Close"].diff()
        gain = delta.clip(lower=0).rolling(window=14).mean()
        loss = (-delta.clip(upper=0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = round(rsi.iloc[-1], 2) if not pd.isna(rsi.iloc[-1]) else None

        # MACD Calculation
        exp1 = data["Close"].ewm(span=12, adjust=False).mean()
        exp2 = data["Close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_value = round((macd.iloc[-1] - signal.iloc[-1]), 4) if len(data) >= 26 else None

        trend = "📈 Bullish" if macd_value and macd_value > 0 else "📉 Bearish" if macd_value else "❓ Neutral"

        return {
            "symbol": symbol.upper(),
            "rsi": rsi_value,
            "macd": macd_value,
            "trend": trend
        }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}
