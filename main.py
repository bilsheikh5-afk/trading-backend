from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
import os

# === your Alpha Vantage API key ===
API_KEY = os.getenv("ALPHAVANTAGE_KEY", "6BQMU6KVJH8QH4TR")

app = FastAPI(title="Trading Backend (Alpha Vantage)")

# === allow your frontend ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "✅ Trading Backend (Alpha Vantage) is live and stable"}

def fetch_data(symbol: str):
    """Fetch data for stocks and crypto using Alpha Vantage."""
    base_url = "https://www.alphavantage.co/query"

    if "-USD" in symbol:  # crypto
        params = {
            "function": "DIGITAL_CURRENCY_DAILY",
            "symbol": symbol.split("-")[0],
            "market": "USD",
            "apikey": API_KEY
        }
        r = requests.get(base_url, params=params, timeout=10)
        data = r.json().get("Time Series (Digital Currency Daily)", {})
        if not data:
            return None
        df = pd.DataFrame(data).T.astype(float)
        df = df.rename(columns={"4a. close (USD)": "Close"})
    else:  # stock
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "apikey": API_KEY,
            "outputsize": "compact"
        }
        r = requests.get(base_url, params=params, timeout=10)
        data = r.json().get("Time Series (Daily)", {})
        if not data:
            return None
        df = pd.DataFrame(data).T.astype(float)
        df = df.rename(columns={"4. close": "Close"})
    
    return df["Close"].iloc[::-1]

def compute_indicators(closes: pd.Series):
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(window=14).mean()
    loss = (-delta.clip(upper=0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_value = round(rsi.iloc[-1], 2)
    exp1 = closes.ewm(span=12, adjust=False).mean()
    exp2 = closes.ewm(span=26, adjust=False).mean()
    macd_line = exp1 - exp2
    signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_value = round(macd_line.iloc[-1] - signal.iloc[-1], 4)
    trend = "📈 Bullish" if macd_value > 0 else "📉 Bearish"
    return rsi_value, macd_value, trend

@app.get("/analyze")
def analyze(symbols: str = Query(..., description="Comma-separated symbols")):
    results = []
    for s in symbols.split(","):
        sym = s.strip().upper()
        try:
            closes = fetch_data(sym)
            if closes is None or len(closes) < 14:
                results.append({"symbol": sym, "error": "No data or insufficient data"})
                continue
            rsi, macd, trend = compute_indicators(closes)
            results.append({"symbol": sym, "rsi": rsi, "macd": macd, "trend": trend})
        except Exception as e:
            results.append({"symbol": sym, "error": str(e)[:120]})
    return {"count": len(results), "data": results}
