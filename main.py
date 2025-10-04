import requests
import pandas as pd
from fastapi import FastAPI

app = FastAPI()

API_KEY = "UgtPrbl46z4iFpolbPTmoEWbyEhx70MV"

@app.get("/")
def root():
    return {"status": "✅ Trading Backend is running!"}

@app.get("/analyze")
def analyze(symbol: str):
    try:
        # Handle crypto using CoinGecko
        if symbol.endswith("-USD") and symbol.split("-")[0].lower() in ["btc", "eth"]:
            coin = symbol.split("-")[0].lower()
            url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
            params = {"vs_currency": "usd", "days": 30}
            r = requests.get(url, params=params)
            if r.status_code != 200:
                return {"symbol": symbol, "error": "Failed to fetch crypto data"}
            data = pd.DataFrame(r.json()["prices"], columns=["timestamp", "Close"])
            data["Close"] = data["Close"].astype(float)
        else:
            # Use FinancialModelingPrep for stocks/forex
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol.upper()}?timeseries=30&apikey={API_KEY}"
            r = requests.get(url)
            json_data = r.json()
            if "historical" not in json_data:
                return {"symbol": symbol, "error": "No data available for this symbol"}
            data = pd.DataFrame(json_data["historical"])
            data.rename(columns={"close": "Close"}, inplace=True)

        # RSI Calculation
        delta = data["Close"].diff()
        gain = delta.clip(lower=0).rolling(window=14).mean()
        loss = (-delta.clip(upper=0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = round(rsi.iloc[-1], 2)

        # MACD Calculation
        exp1 = data["Close"].ewm(span=12, adjust=False).mean()
        exp2 = data["Close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_value = round(macd.iloc[-1] - signal.iloc[-1], 4)

        trend = "📈 Bullish" if macd_value > 0 else "📉 Bearish"

        return {
            "symbol": symbol.upper(),
            "rsi": rsi_value,
            "macd": macd_value,
            "trend": trend
        }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}
