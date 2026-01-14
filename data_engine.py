import requests
import yfinance as yf
from bs4 import BeautifulSoup
import time

HEADERS = {"User-Agent": "Mozilla/5.0"}

# -----------------------------
# PERSISTENT IN-MEMORY CACHE
# -----------------------------
CACHE = {}
CACHE_TTL = 6 * 60 * 60  # 6 hours

def now():
    return int(time.time())

def safe_float(x):
    try:
        return float(x)
    except:
        return None

# -----------------------------
# YAHOO (SAFE + OPTIONAL)
# -----------------------------
def get_yahoo(stock):
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
        return None  # IMPORTANT: DO NOT THROW


# -----------------------------
# SCREENER (SAFE + OPTIONAL)
# -----------------------------
def get_screener(stock):
    try:
        r = requests.get(
            f"https://www.screener.in/company/{stock}/",
            headers=HEADERS,
            timeout=10
        )

        if r.status_code != 200:
            return None

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
        return None  # IMPORTANT: DO NOT THROW


# -----------------------------
# MAIN ANALYZE (ERROR-PROOF)
# -----------------------------
def analyze(stock):
    stock = stock.strip().upper()

    # ✅ SERVE FROM CACHE IF EXISTS
    if stock in CACHE and now() - CACHE[stock]["ts"] < CACHE_TTL:
        return CACHE[stock]["data"]

    # Throttle requests (CRITICAL)
    time.sleep(1.5)

    y = get_yahoo(stock)
    s = get_screener(stock)

    # ❌ BOTH FAILED → return last cached OR graceful message
    if y is None and s is None:
        if stock in CACHE:
            return CACHE[stock]["data"]

        return {
            "Stock": stock,
            "Verdict": "WATCH",
            "Score": 0,
            "Interpretation": "Data temporarily unavailable (rate limited)"
        }

    # Fallbacks
    y = y or {}
    s = s or {}

    score = 0
    remarks = []

    if s.get("roce") and s["roce"] >= 15:
        score += 2
    else:
        remarks.append("Weak ROCE")

    if y.get("cash_flow"):
        score += 1
    else:
        remarks.append("Weak cash flow")

    if y.get("debt_equity") is None or y.get("debt_equity") <= 0.7:
        score += 1
    else:
        remarks.append("High debt")

    if y.get("roe") and y["roe"] >= 15:
        score += 1
    else:
        remarks.append("Low ROE")

    if y.get("profit_growth") and y["profit_growth"] >= 10:
        score += 1

    if y.get("pe") and y["pe"] <= 25:
        score += 1

    if y.get("dividend_yield") and y["dividend_yield"] >= 1:
        score += 1

    verdict = "BUY" if score >= 6 else "WATCH" if score >= 4 else "AVOID"

    result = {
        "Stock": stock,
        "Verdict": verdict,
        "Score": score,

        "ROCE": s.get("roce"),
        "ROE": y.get("roe"),
        "Profit Growth": y.get("profit_growth"),
        "Sales Growth": y.get("sales_growth"),

        "Debt": s.get("debt"),
        "Debt / Equity": y.get("debt_equity"),

        "Cash Flow": y.get("cash_flow"),

        "P/E": y.get("pe"),
        "PEG": y.get("peg"),

        "Book Value": s.get("book_value"),
        "P/B": round(y["price"] / s["book_value"], 2)
            if y.get("price") and s.get("book_value") else None,

        "Intrinsic Value": s.get("intrinsic"),

        "Dividend Yield": y.get("dividend_yield"),

        "52W High": y.get("52w_high"),
        "52W Low": y.get("52w_low"),

        "Price": y.get("price"),
        "Market Cap": y.get("market_cap"),

        "Interpretation": ", ".join(remarks) or "Data fetched with partial sources"
    }

    CACHE[stock] = {"ts": now(), "data": result}
    return result
