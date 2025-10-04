from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import yfinance as yf
from binance.client import Client
import random
import os

app = FastAPI(title="Live Trading Advisor API")

# Allow your frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "healthy"}

@app.get("/api/analyze")
def analyze():
    """Mock real-time analysis using Binance & Yahoo data"""
    results = []

    # Live crypto data from Binance
    try:
        crypto_data = yf.download("BTC-USD", period="1d", interval="1h")
        if not crypto_data.empty:
            last_price = crypto_data["Close"].iloc[-1]
            results.append({
                "symbol": "BTC/USDT",
                "direction": random.choice(["BUY", "SELL"]),
                "price": round(float(last_price), 2),
                "rsi": round(random.uniform(30, 70), 2),
                "score": round(random.uniform(60, 95), 2),
            })
    except Exception as e:
        results.append({"error": f"Crypto data fetch failed: {e}"})

    # Live forex data
    try:
        forex_data = yf.download("EURUSD=X", period="1d", interval="1h")
        if not forex_data.empty:
            last_price = forex_data["Close"].iloc[-1]
            results.append({
                "symbol": "EUR/USD",
                "direction": random.choice(["BUY", "SELL"]),
                "price": round(float(last_price), 4),
                "rsi": round(random.uniform(30, 70), 2),
                "score": round(random.uniform(60, 95), 2),
            })
    except Exception as e:
        results.append({"error": f"Forex data fetch failed: {e}"})

    return {"success": True, "signals_found": len(results), "data": results}
