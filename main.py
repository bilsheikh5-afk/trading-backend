from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests, pandas as pd, os

API_KEY = os.getenv("ALPHAVANTAGE_KEY", "6BQMU6KVJH8QH4TR")

app = FastAPI(title="Trading Backend (Alpha Vantage — Stocks + Crypto)")

# Allow any frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "✅ Alpha Vantage backend live"}

# --- Helpers ---------------------------------------------------
def fetch_data(symbol: str):
    base = "https://www.alphavantage.co/query"
    # Crypto handling
    if "-USD" in symbol:
        coin = symbol.split("-")[0]
        params = {
            "function": "DIGITAL_CURRENCY_DAILY",
            "symbol": coin,
            "market": "USD",
            "apikey": API_KEY
        }
        r = requests.get(base, params=params, timeout=15)
        data = r.json().get("Time Series (Digital Currency Daily)", {})
        if not data:
            return None
        df = pd.DataFrame(data).T
        df["Close"] = df["4a. close (USD)"].astype(float)
    else:
        # Stock handling
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "apikey": API_KEY,
            "outputsize": "compact"
        }
        r = requests.get(base, params=params, timeout=15)
        data = r.json().get("Time Series (Daily)", {})
        if not data:
            return None
        df = pd.DataFrame(data).T
        df["Close"] = df["4. close"].astype(float)
    return df["Close"].iloc[::-1]

def compute_indicators(closes: pd.Series):
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_val = round(rsi.iloc[-1], 2)
    exp1 = closes.ewm(span=12, adjust=False).mean()
    exp2 = closes.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    macd_val = round(macd.iloc[-1] - signal.iloc[-1], 4)
    trend = "📈 Bullish" if macd_val > 0 else "📉 Bearish"
    return rsi_val, macd_val, trend
# ---------------------------------------------------------------

@app.get("/analyze")
def analyze(symbols: str = Query(...)):
    out = []
    for sym in symbols.split(","):
        s = sym.strip().upper()
        try:
            closes = fetch_data(s)
            if closes is None or len(closes) < 14:
                out.append({"symbol": s, "error": "No data or insufficient data"})
                continue
            rsi, macd, trend = compute_indicators(closes)
            out.append({"symbol": s, "rsi": rsi, "macd": macd, "trend": trend})
        except Exception as e:
            out.append({"symbol": s, "error": str(e)[:100]})
    return {"count": len(out), "data": out}
