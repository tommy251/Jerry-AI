"""
Stock Analysis Agent - 100% Free
Uses yfinance (Yahoo Finance) — no API key needed ever
"""

import re
import yfinance as yf
from .brain import chat


TICKER_MAP = {
    "apple": "AAPL", "tesla": "TSLA", "google": "GOOGL", "alphabet": "GOOGL",
    "microsoft": "MSFT", "amazon": "AMZN", "nvidia": "NVDA", "meta": "META",
    "netflix": "NFLX", "bitcoin": "BTC-USD", "ethereum": "ETH-USD",
    "sp500": "^GSPC", "s&p": "^GSPC", "dow": "^DJI", "nasdaq": "^IXIC",
    "gold": "GC=F", "oil": "CL=F", "nike": "NKE", "disney": "DIS",
    "uber": "UBER", "airbnb": "ABNB", "palantir": "PLTR", "amd": "AMD",
    "intel": "INTC", "ford": "F", "gm": "GM", "coca cola": "KO",
    "pepsi": "PEP", "walmart": "WMT", "shopify": "SHOP",
}


class StockAgent:
    def __init__(self):
        pass

    async def initialize(self):
        pass

    async def run(self, query: str) -> str:
        ticker = self._extract_ticker(query)
        if not ticker:
            return f"Could not identify a stock ticker in: '{query}'. Try being more specific, e.g. 'Analyze AAPL stock'."

        data = self._fetch_data(ticker)
        if "error" in data:
            return f"Stock data error for {ticker}: {data['error']}"

        return self._analyse(ticker, data, query)

    def _extract_ticker(self, query: str) -> str:
        lower = query.lower()
        for name, ticker in TICKER_MAP.items():
            if name in lower:
                return ticker
        # Look for explicit uppercase ticker (1-5 chars)
        matches = re.findall(r'\b[A-Z]{1,5}\b', query)
        skip = {"AI", "NBA", "NFL", "THE", "AND", "FOR", "TOM"}
        valid = [m for m in matches if m not in skip]
        return valid[0] if valid else ""

    def _fetch_data(self, ticker: str) -> dict:
        try:
            stock = yf.Ticker(ticker)
            hist  = stock.history(period="3mo")
            info  = stock.info

            if hist.empty:
                return {"error": "No price data found"}

            close   = hist["Close"]
            current = float(close.iloc[-1])
            start   = float(close.iloc[0])
            pct_chg = round(((current - start) / start) * 100, 2)

            # Technical indicators
            sma20 = round(float(close.tail(20).mean()), 2)
            sma50 = round(float(close.tail(50).mean()), 2) if len(close) >= 50 else None

            # RSI 14
            delta = close.diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean()
            rs    = gain / loss
            rsi   = round(float(100 - (100 / (1 + rs.iloc[-1]))), 2)

            # Volume trend
            avg_vol   = int(hist["Volume"].tail(20).mean())
            latest_vol = int(hist["Volume"].iloc[-1])
            vol_signal = "Above average" if latest_vol > avg_vol * 1.2 else \
                         "Below average" if latest_vol < avg_vol * 0.8 else "Normal"

            return {
                "ticker":        ticker,
                "current_price": round(current, 2),
                "3mo_change":    f"{pct_chg}%",
                "sma_20":        sma20,
                "sma_50":        sma50 or "N/A",
                "rsi_14":        rsi,
                "rsi_signal":    "Oversold (buy zone)" if rsi < 30 else
                                 "Overbought (caution)" if rsi > 70 else "Neutral",
                "volume":        vol_signal,
                "52w_high":      info.get("fiftyTwoWeekHigh", "N/A"),
                "52w_low":       info.get("fiftyTwoWeekLow", "N/A"),
                "pe_ratio":      info.get("trailingPE", "N/A"),
                "market_cap":    f"${round(info.get('marketCap', 0) / 1e9, 1)}B",
                "sector":        info.get("sector", "N/A"),
                "company":       info.get("longName", ticker),
            }
        except Exception as e:
            return {"error": str(e)}

    def _analyse(self, ticker: str, data: dict, query: str) -> str:
        prompt = f"""Tom asked about: {query}

Stock data for {data['company']} ({ticker}):
{chr(10).join(f"  {k}: {v}" for k, v in data.items())}

Give Tom a complete stock analysis:
1. Quick snapshot — where the stock stands right now
2. Technical signals — what RSI, SMAs and volume are telling us
3. Bull case vs Bear case (2 points each)
4. Short-term outlook (1-2 weeks): Bullish / Neutral / Bearish
5. One-line action signal

Be sharp and direct. This is analysis, not financial advice — remind Tom of that briefly."""

        return chat(
            [{"role": "user", "content": prompt}],
            system="You are Jerry, Tom's elite financial analyst AI. Be direct, data-driven, and sharp."
        )
