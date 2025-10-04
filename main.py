from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import requests
import pandas as pd
from fastapi import FastAPI
import yfinance as yf
import pandas as pd

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Backend running ✅"}

@app.get("/analyze")
def analyze(symbol: str):
    try:
        data = yf.download(symbol, period="3mo", interval="1d")
        if data.empty:
            return {"error": f"No data found for {symbol}"}

        # Calculate RSI
        delta = data["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = round(rsi.iloc[-1], 2)

        # Calculate MACD
        exp1 = data["Close"].ewm(span=12, adjust=False).mean()
        exp2 = data["Close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_value = round(macd.iloc[-1] - signal.iloc[-1], 4)

        return {"symbol": symbol, "rsi": rsi_value, "macd": macd_value}
    except Exception as e:
        return {"error": str(e)}
def fetch_ticker_data(symbol: str):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1h&range=1d"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"⚠️ Failed download: {symbol} ({response.status_code})")
            return pd.DataFrame()
        
        data = response.json()
        if "chart" not in data or "result" not in data["chart"]:
            print(f"⚠️ Invalid JSON format for {symbol}")
            return pd.DataFrame()
        
        timestamps = data["chart"]["result"][0]["timestamp"]
        close_prices = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        df = pd.DataFrame({"timestamp": timestamps, "close": close_prices})
        return df
    
    except Exception as e:
        print(f"❌ Failed to get {symbol}: {e}")
        return pd.DataFrame()
import time
import threading

app = FastAPI(
    title="Live Trading Advisor (v4.0)",
    description="Multi-symbol real-time trading analysis with cache & history",
    version="4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change to your frontend URL for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==== CACHE + HISTORY ====
REFRESH_INTERVAL = 300  # 5 minutes
HISTORY_LIMIT = 10      # Keep last 10 snapshots (~50 minutes)

cache_data = {}
cache_history = []
cache_timestamp = 0
cache_lock = threading.Lock()

# ===== Helper Functions =====
def fetch_symbol_data(symbol):
    """Fetch RSI/MACD for a given symbol from Yahoo Finance."""
    try:
        data = yf.download(symbol, period="60d", interval="1h", progress=False)
        if data.empty:
            return {"symbol": symbol, "error": "No data"}

        # RSI Calculation
        delta = data["Close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        data["RSI"] = 100 - (100 / (1 + rs))

        # MACD Calculation
        data["EMA12"] = data["Close"].ewm(span=12, adjust=False).mean()
        data["EMA26"] = data["Close"].ewm(span=26, adjust=False).mean()
        data["MACD"] = data["EMA12"] - data["EMA26"]
        data["Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()

        latest = data.iloc[-1]
        rsi = round(latest["RSI"], 2)
        macd = round(latest["MACD"], 4)
        signal = round(latest["Signal"], 4)
        price = round(latest["Close"], 2)

        if rsi < 30 and macd > signal:
            advice = "📈 Strong Buy"
        elif rsi > 70 and macd < signal:
            advice = "📉 Strong Sell"
        else:
            advice = "⚖️ Hold"

        return {
            "symbol": symbol,
            "price": price,
            "RSI": rsi,
            "MACD": macd,
            "Signal": signal,
            "Advice": advice
        }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


def update_cache():
    """Refresh cache & store history snapshots."""
    global cache_data, cache_timestamp, cache_history

    with cache_lock:
        symbols = cache_data.get("symbols", ["BTC-USD", "ETH-USD", "EURUSD=X", "AAPL"])
        new_results = [fetch_symbol_data(s) for s in symbols]

        cache_data = {
            "timestamp": time.time(),
            "results": new_results
        }
        cache_timestamp = cache_data["timestamp"]

        # Keep latest 10 history entries
        snapshot = {
            "time": time.ctime(cache_timestamp),
            "results": new_results
        }
        cache_history.append(snapshot)
        if len(cache_history) > HISTORY_LIMIT:
            cache_history.pop(0)

        print(f"✅ Cache updated at {time.ctime(cache_timestamp)} ({len(cache_history)} snapshots stored)")


def cache_refresher():
    """Background thread to refresh every REFRESH_INTERVAL seconds."""
    while True:
        update_cache()
        time.sleep(REFRESH_INTERVAL)

# Start background thread
threading.Thread(target=cache_refresher, daemon=True).start()

# ===== Routes =====

@app.get("/")
def root():
    return {"message": "✅ Live Trading Advisor backend running", "version": "4.0"}

@app.get("/api/analyze")
def analyze(symbols: str = Query("BTC-USD,ETH-USD,EURUSD=X,AAPL")):
    """Return current analysis for given symbols."""
    global cache_data, cache_timestamp
    user_symbols = [s.strip().upper() for s in symbols.split(",")]

    # Update cache manually if too old
    if time.time() - cache_timestamp > REFRESH_INTERVAL:
        update_cache()

    results = []
    for symbol in user_symbols:
        cached = next((r for r in cache_data.get("results", []) if r.get("symbol") == symbol), None)
        results.append(cached or fetch_symbol_data(symbol))

    return {
        "requested": user_symbols,
        "cached_at": time.ctime(cache_timestamp),
        "results": results
    }

@app.get("/api/history")
def history():
    """Return last 10 cache snapshots."""
    return {
        "count": len(cache_history),
        "interval_seconds": REFRESH_INTERVAL,
        "history": cache_history
    }

@app.get("/api/status")
def status():
    """Health check."""
    return {
        "status": "ok",
        "cached_at": time.ctime(cache_timestamp),
        "snapshots": len(cache_history),
        "symbols_tracked": [r.get("symbol") for r in cache_data.get("results", [])]
    }
