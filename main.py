from fastapi import FastAPI
import yfinance as yf
import pandas as pd

app = FastAPI()

@app.get("/")
def root():
    return {"status": "✅ Backend running successfully"}

@app.get("/analyze")
def analyze(symbol: str):
    try:
        # Use a smaller data period (more reliable for Render)
        data = yf.download(symbol, period="1mo", interval="1d", progress=False)

        if data is None or data.empty:
            return {"symbol": symbol, "error": "No data available from Yahoo Finance"}

        # RSI calculation
        delta = data["Close"].diff()
        gain = delta.clip(lower=0).rolling(window=14).mean()
        loss = (-delta.clip(upper=0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = round(rsi.iloc[-1], 2)

        # MACD calculation
        exp1 = data["Close"].ewm(span=12, adjust=False).mean()
        exp2 = data["Close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_value = round(macd.iloc[-1] - signal.iloc[-1], 4)

        trend = "Bullish 📈" if macd_value > 0 else "Bearish 📉"

        return {
            "symbol": symbol,
            "rsi": rsi_value,
            "macd": macd_value,
            "trend": trend
        }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}
