import requests
import yfinance as yf
from bs4 import BeautifulSoup
import time

HEADERS = {"User-Agent": "Mozilla/5.0"}

# -----------------------------
# SIMPLE IN-MEMORY CACHE
# -----------------------------
CACHE = {}
CACHE_TTL = 60 * 60  # 1 hour

def now():
    return int(time.time())

def safe_float(x):
    try:
        return float(x)
    except:
        return None

# -----------------------------
# YAHOO SAFE FETCH
# -----------------------------
def get_yahoo_safe(stock):
    try:
        t = yf.Ticker(f"{stock}.NS")
        info = t.info or {}

        hist = t.history(period="1y")
        price = high_52w = low_52w = None
        if not hist.empty:
            price = round(hist["Close"].iloc[-1], 2)
            high_52w = round(hist["High"].max(), 2)
            low_52w = round(hist["Low"].min(), 2)

        market_cap = info.get("marketCap")
        market_cap = round(market_cap / 1e7, 2) if market_cap else None

        raw_div = info.get("dividendYield")
        dividend_yield = None
        if raw_div:
            dividend_yield = round(raw_div * 100, 2) if raw_div < 1 else round(raw_div, 2)

        raw_cf = info.get("operatingCashflow")
        cash_flow = round(raw_cf / 1e7, 2) if raw_cf else None

        return {
            "price": price,
            "52w_high": high_52w,
            "52w_low": low_52w,
            "market_cap": market_cap,
            "pe": info.get("trailingPE"),
            "peg": info.get("pegRatio"),
            "pb": info.get("priceToBook"),
            "roe": round(info.get("returnOnEquity", 0) * 100, 2)
                if info.get("returnOnEquity") else None,
            "profit_growth": round(info.get("earningsGrowth", 0) * 100, 2)
                if info.get("earningsGrowth") else None,
            "sales_growth": round(info.get("revenueGrowth", 0) * 100, 2)
                if info.get("revenueGrowth") else None,
            "debt_equity": info.get("debtToEquity"),
            "cash_flow": cash_flow,
            "dividend_yield": dividend_yield
        }

    except:
        raise Exception("Yahoo rate limited")

# -----------------------------
# SCREENER SAFE FETCH
# -----------------------------
def get_screener_safe(stock):
    try:
        r = requests.get(
            f"https://www.screener.in/company/{stock}/",
            headers=HEADERS,
            timeout=10
        )

        if r.status_code == 429:
            raise Exception("Screener rate limited")

        soup = BeautifulSoup(r.text, "lxml")
        data = {}

        for li in soup.select("li"):
            k = li.find("span", class_="name")
            v = li.find("span", class_="value")
            if k and v:
                data[k.text.strip()] = v.text.strip()

        return {
            "roce": safe_float(data.get("ROCE", "").replace("%", "")),
            "debt": safe_float(data.get("Debt", "").replace("₹", "").replace(",", "")),
            "book_value": safe_float(data.get("Book Value", "").replace("₹", "")),
            "intrinsic": safe_float(data.get("Intrinsic Value", "").replace("₹", ""))
        }

    except:
        raise Exception("Screener rate limited")

# -----------------------------
# MAIN ANALYZE FUNCTION (CACHED)
# -----------------------------
def analyze(stock):
    stock = stock.strip().upper()

    # 🔥 RETURN FROM CACHE IF AVAILABLE
    if stock in CACHE:
        cached = CACHE[stock]
        if now() - cached["ts"] < CACHE_TTL:
            return cached["data"]

    try:
        y = get_yahoo_safe(stock)
        s = get_screener_safe(stock)

        score = 0
        remarks = []

        if s["roce"] and s["roce"] >= 15:
            score += 2
        else:
            remarks.append("Weak ROCE")

        if y["cash_flow"] and y["cash_flow"] > 0:
            score += 1
        else:
            remarks.append("Weak cash flow")

        if y["debt_equity"] is None or y["debt_equity"] <= 0.7:
            score += 1
        else:
            remarks.append("High debt")

        if y["roe"] and y["roe"] >= 15:
            score += 1
        else:
            remarks.append("Low ROE")

        if y["profit_growth"] and y["profit_growth"] >= 10:
            score += 1

        if y["pe"] and y["pe"] <= 25:
            score += 1
        else:
            remarks.append("Expensive valuation")

        if y["dividend_yield"] and y["dividend_yield"] >= 1:
            score += 1

        if y["price"] and y["52w_high"] and y["price"] <= 0.9 * y["52w_high"]:
            score += 1
        else:
            remarks.append("Near 52W high")

        verdict = "BUY" if score >= 6 else "WATCH" if score >= 4 else "AVOID"

        result = {
            "Stock": stock,
            "Verdict": verdict,
            "Score": score,

            "ROCE": s["roce"],
            "ROE": y["roe"],
            "Profit Growth": y["profit_growth"],
            "Sales Growth": y["sales_growth"],

            "Debt": s["debt"] if s["debt"] is not None else y["debt_equity"],
            "Debt / Equity": y["debt_equity"],

            "Cash Flow": y["cash_flow"],

            "P/E": y["pe"],
            "PEG": y["peg"],

            "Book Value": s["book_value"],
            "P/B": round(y["price"] / s["book_value"], 2)
                if y["price"] and s["book_value"] else None,

            "Intrinsic Value": s["intrinsic"],

            "Dividend Yield": y["dividend_yield"],

            "52W High": y["52w_high"],
            "52W Low": y["52w_low"],

            "Price": y["price"],
            "Market Cap": y["market_cap"],

            "Interpretation": ", ".join(remarks) or "Strong fundamentals"
        }

        CACHE[stock] = {"ts": now(), "data": result}
        return result

    except Exception as e:
        return {
            "Stock": stock,
            "Verdict": "ERROR",
            "Score": 0,
            "Interpretation": "Too Many Requests. Rate limited. Try after a while."
        }
