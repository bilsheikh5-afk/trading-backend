from fastapi import FastAPI
import yfinance as yf
import pandas as pd

app = FastAPI()

@app.get("/")
def root():
    return {"status": "✅ Backend is running properly!"}

@app.get("/analyze")
def analyze(symbol: str):
    try:
        data = yf.download(symbol, period="3mo", interval="1d")
        if data.empty:
            return {"symbol": symbol, "error": "No data available"}

        # RSI Calculation
        delta = data["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = round(rsi.iloc[-1], 2)

        # MACD Calculation
        exp1 = data["Close"].ewm(span=12, adjust=False).mean()
        exp2 = data["Close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_value = round(macd.iloc[-1] - signal.iloc[-1], 4)

        return {
            "symbol": symbol,
            "rsi": rsi_value,
            "macd": macd_value,
            "trend": "Bullish 📈" if macd_value > 0 else "Bearish 📉"
        }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}
