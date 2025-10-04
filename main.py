# path: main.py
import pandas as pd
import yfinance as yf
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Trading Backend - Yahoo Finance", version="2.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "✅ Trading Backend (Yahoo Finance) is live and stable"}


@app.get("/analyze")
def analyze(symbol: str):
    """
    Analyze a symbol (crypto, stock, or forex) using Yahoo Finance.
    Computes RSI and MACD indicators.
    """
    try:
        # Normalize input
        symbol = symbol.upper().strip()

        # Common alias correction
        symbol_map = {
            "BTC-USD": "BTC-USD",
            "ETH-USD": "ETH-USD",
            "EURUSD": "EURUSD=X",
            "EURUSD=X": "EURUSD=X",
            "AAPL": "AAPL",
        }
        yf_symbol = symbol_map.get(symbol, symbol)

        # Fetch data (last 90 days)
        data = yf.download(yf_symbol, period="90d", interval="1d", progress=False)

        if data.empty:
            return {"symbol": symbol, "error": "No valid data found (symbol not recognized)"}

        # --- RSI Calculation ---
        data["delta"] = data["Close"].diff()
        gain = data["delta"].clip(lower=0).rolling(window=14).mean()
        loss = -data["delta"].clip(upper=0).rolling(window=14).mean()
        rs = gain / loss
        data["RSI"] = 100 - (100 / (1 + rs))
        rsi_value = round(data["RSI"].iloc[-1], 2)

        # --- MACD Calculation ---
        exp1 = data["Close"].ewm(span=12, adjust=False).mean()
        exp2 = data["Close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_value = round(macd.iloc[-1] - signal.iloc[-1], 4)

        # --- Trend ---
        trend = "📈 Bullish" if macd_value > 0 else "📉 Bearish"

        return {
            "symbol": symbol,
            "rsi": rsi_value,
            "macd": macd_value,
            "trend": trend,
            "source": "Yahoo Finance"
        }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}
