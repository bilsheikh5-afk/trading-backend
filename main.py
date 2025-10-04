import yfinance as yf
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Trading Backend (FastAPI + yfinance)")

# === CORS (important for your frontend) ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ You can restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "✅ Trading Backend (Yahoo Finance) is live and stable"}

def analyze_single(symbol: str):
    """Compute RSI and MACD for one symbol."""
    try:
        original_symbol = symbol.strip().upper()

        # Normalize symbol
        if original_symbol.endswith("=AAPL"):   # weird input like EURUSD=AAPL
            return analyze_single("EURUSD=X"), analyze_single("AAPL")

        if "=" in original_symbol and not original_symbol.endswith("=X"):
            original_symbol = original_symbol.split("=")[0] + "=X"

        # Download OHLCV
        data = yf.download(original_symbol, period="30d", progress=False)
        if data.empty:
            return {"symbol": symbol, "error": f"No data for {original_symbol}"}

        closes = data["Close"].dropna()
        if len(closes) < 14:
            return {"symbol": symbol, "error": "Insufficient data (<14 periods)"}

        # RSI (14)
        delta = closes.diff()
        gain = delta.clip(lower=0).rolling(window=14).mean()
        loss = (-delta.clip(upper=0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = round(rsi.iloc[-1], 2)

        # MACD (12/26/9)
        exp1 = closes.ewm(span=12, adjust=False).mean()
        exp2 = closes.ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_value = round(macd_line.iloc[-1] - signal.iloc[-1], 4)

        trend = "📈 Bullish" if macd_value > 0 else "📉 Bearish"

        return {"symbol": symbol, "rsi": rsi_value, "macd": macd_value, "trend": trend}

    except Exception as e:
        return {"symbol": symbol, "error": f"Fetch failed: {str(e)[:100]}"}

@app.get("/analyze")
def analyze(symbols: str = Query(..., description="Comma-separated list: e.g. BTC-USD,ETH-USD,EURUSD=X")):
    """
    Analyze one or more symbols: /analyze?symbols=BTC-USD,ETH-USD
    """
    result = []
    for s in symbols.split(","):
        s = s.strip()
        if not s:
            continue
        result.append(analyze_single(s))
    return {"count": len(result), "data": result}
