from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests, pandas as pd, os

API_KEY = os.getenv("ALPHAVANTAGE_KEY", "6BQMU6KVJH8QH4TR")  # Set as env var in Render for security

app = FastAPI(title="Trading Backend (Alpha Vantage — Stocks + Crypto + Forex)")

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
    return {"status": "✅ Alpha Vantage backend live", "key_set": bool(os.getenv("ALPHAVANTAGE_KEY"))}

# --- Helpers ---------------------------------------------------
def fetch_data(symbol: str):
    base = "https://www.alphavantage.co/query"
    params_base = {"apikey": API_KEY, "outputsize": "compact"}
    
    # Crypto handling (e.g., BTC-USD)
    if "-USD" in symbol:
        coin = symbol.split("-")[0]
        params = {**params_base, "function": "DIGITAL_CURRENCY_DAILY", "symbol": coin, "market": "USD"}
        r = requests.get(base, params=params, timeout=15)
        data_key = "Time Series (Digital Currency Daily)"
        close_key = "4a. close (USD)"
    # Forex handling (e.g., EURUSD=X)
    elif "=X" in symbol:
        pair = symbol.replace("=X", "")  # e.g., EURUSD
        from_sym = pair[:3]
        to_sym = pair[3:]
        params = {**params_base, "function": "FX_DAILY", "from_symbol": from_sym, "to_symbol": to_sym}
        r = requests.get(base, params=params, timeout=15)
        data_key = "Time Series FX (Daily)"
        close_key = "4. close"
    # Stock handling (e.g., AAPL)
    else:
        params = {**params_base, "function": "TIME_SERIES_DAILY", "symbol": symbol}  # Free endpoint
        r = requests.get(base, params=params, timeout=15)
        data_key = "Time Series (Daily)"
        close_key = "4. close"
    
    json_data = r.json()
    if "Error Message" in json_data or "Note" in json_data:
        return None  # API error (e.g., rate limit, invalid key)
    
    data = json_data.get(data_key, {})
    if not data:
        return None
    
    df = pd.DataFrame(data).T
    df["Close"] = df[close_key].astype(float)
    return df["Close"].iloc[::-1]  # Chronological order

def compute_indicators(closes: pd.Series):
    if len(closes) < 14:
        raise ValueError("Insufficient data for indicators (need >=14 periods)")
    
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
    macd_val = round((macd.iloc[-1] - signal.iloc[-1]), 4)  # Histogram value
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
            if closes is None:
                out.append({"symbol": s, "error": "API error (check key/limits)"})
                continue
            if len(closes) < 14:
                out.append({"symbol": s, "error": "Insufficient data points"})
                continue
            rsi, macd, trend = compute_indicators(closes)
            out.append({"symbol": s, "rsi": rsi, "macd": macd, "trend": trend})
        except Exception as e:
            out.append({"symbol": s, "error": str(e)[:100]})
    return {"count": len(out), "data": out}
