import yfinance as yf
import pandas as pd
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "✅ Trading Backend (Yahoo Finance) is live and stable"}

@app.get("/analyze")
def analyze(symbol: str):
    try:
        original_symbol = symbol
        # Normalize: Handle =X for forex, split malformed like EURUSD=AAPL
        if "=" in symbol:
            if symbol.endswith("=AAPL"):  # Fix common typo
                return analyze("EURUSD=X") | analyze("AAPL")  # Recursive, but simple dict merge
            symbol = symbol.split("=")[0] + "=X" if len(symbol.split("=")[0]) == 6 else symbol.replace("=", "-")  # EURUSD= -> EURUSD=X; others to -

        # Yfinance fetch (works for BTC-USD, AAPL, EURUSD=X)
        data = yf.download(symbol, period="30d", progress=False)
        if data.empty:
            return {"symbol": original_symbol, "error": f"No data for {symbol} (invalid symbol? Try BTC-USD or EURUSD=X)"}
        closes = data["Close"].dropna()
        if len(closes) < 14:
            return {"symbol": original_symbol, "error": "Insufficient data (<14 periods)"}
        data = pd.DataFrame({"Close": closes})

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
        macd_value = round((macd_line.iloc[-1] - signal.iloc[-1]), 4)

        trend = "📈 Bullish" if macd_value > 0 else "📉 Bearish"

        return {
            "symbol": original_symbol.upper(),
            "rsi": rsi_value,
            "macd": macd_value,
            "trend": trend
        }

    except Exception as e:
        return {"symbol": original_symbol, "error": f"Fetch failed: {str(e)[:100]} (check symbol format)"}
