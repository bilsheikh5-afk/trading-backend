# path: main.py
import requests
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Trading Backend", version="1.1")

# Allow frontend connections (important for browsers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your frontend domain for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = "UgtPrbl46z4iFpolbPTmoEWbyEhx70MV"

@app.get("/")
def root():
    return {"status": "✅ Trading Backend is live and stable"}

@app.get("/analyze")
def analyze(symbol: str):
    """
    Analyze a trading symbol (crypto, stock, or forex)
    Computes RSI and MACD indicators.
    """
    try:
        symbol = symbol.upper().replace(" ", "")
        url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}?timeseries=60&apikey={API_KEY}"
        r = requests.get(url)
        data_json = r.json()

        if "historical" not in data_json or len(data_json["historical"]) < 20:
            return {"symbol": symbol, "error": "No valid data found (check symbol or API limit)"}

        data = pd.DataFrame(data_json["historical"])
        data.rename(columns={"close": "Close"}, inplace=True)
        data = data[::-1]  # reverse order (oldest → latest)

        delta = data["Close"].diff()
        gain = delta.clip(lower=0).rolling(window=14).mean()
        loss = (-delta.clip(upper=0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = round(rsi.iloc[-1], 2)

        exp1 = data["Close"].ewm(span=12, adjust=False).mean()
        exp2 = data["Close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_value = round(macd.iloc[-1] - signal.iloc[-1], 4)

        trend = "📈 Bullish" if macd_value > 0 else "📉 Bearish"

        return {
            "symbol": symbol,
            "rsi": rsi_value,
            "macd": macd_value,
            "trend": trend
        }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}
