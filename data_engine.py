import requests
import yfinance as yf
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}

def safe_float(x):
    try:
        return float(x)
    except:
        return None

# -----------------------------
# YAHOO (CLOUD SAFE)
# -----------------------------
def get_yahoo(stock):
    t = yf.Ticker(f"{stock}.NS")

    # ✅ ALWAYS WORKS
    hist = t.history(period="1y")
    price = None
    high_52w = None
    low_52w = None

    if not hist.empty:
        price = round(hist["Close"].iloc[-1], 2)
        high_52w = round(hist["High"].max(), 2)
        low_52w = round(hist["Low"].min(), 2)

    # ✅ FAST_INFO (NOT BLOCKED)
    fi = t.fast_info or {}
    shares = fi.get("sharesOutstanding")

    market_cap_cr = None
    if price and shares:
        market_cap_cr = round((price * shares) / 1e7, 2)

    # ⚠️ OPTIONAL (may be blocked, ok if missing)
    info = t.info or {}
    pe = info.get("trailingPE")
    roe = (
        round(info.get("returnOnEquity") * 100, 2)
        if info.get("returnOnEquity") else None
    )

    raw_div = info.get("dividendYield")
    if raw_div is None:
        div_yield = None
    elif raw_div > 1:
        div_yield = round(raw_div, 2)
    else:
        div_yield = round(raw_div * 100, 2)

    return {
        "price": price,
        "52w_high": high_52w,
        "52w_low": low_52w,
        "market_cap_cr": market_cap_cr,
        "pe": pe,
        "roe": roe,
        "div_yield": div_yield,
        "debt_equity": info.get("debtToEquity")
    }

# -----------------------------
# SCREENER (BOOK VALUE + ROCE)
# -----------------------------
def get_screener(stock):
    try:
        r = requests.get(
            f"https://www.screener.in/company/{stock}/",
            headers=HEADERS,
            timeout=10
        )
        soup = BeautifulSoup(r.text, "lxml")

        data = {}
        for li in soup.select("li"):
            k = li.find("span", class_="name")
            v = li.find("span", class_="value")
            if k and v:
                data[k.text.strip()] = v.text.strip()

        roce = safe_float(data.get("ROCE", "").replace("%", ""))
        book_value = safe_float(data.get("Book Value", "").replace("₹", ""))
        face_value = data.get("Face Value")

        return {
            "roce": roce,
            "book_value": book_value,
            "face_value": face_value
        }
    except:
        return {
            "roce": None,
            "book_value": None,
            "face_value": None
        }

# -----------------------------
# ANALYSIS + SCORE
# -----------------------------
def analyze(stock):
    if not stock or not stock.strip():
        return None

    stock = stock.strip().upper()

    y = get_yahoo(stock)
    s = get_screener(stock)

    score = 0
    remarks = []

    if y["roe"] and y["roe"] >= 15:
        score += 1
    else:
        remarks.append("Low ROE")

    if s["roce"] and s["roce"] >= 15:
        score += 1
    else:
        remarks.append("Low ROCE")

    if y["pe"] and y["pe"] <= 25:
        score += 1
    else:
        remarks.append("High PE")

    if (y["debt_equity"] is None or y["debt_equity"] <= 1) or (s["roce"] and s["roce"] >= 25):
        score += 1
    else:
        remarks.append("High Debt")

    if y["div_yield"] and y["div_yield"] >= 1:
        score += 1
    else:
        remarks.append("Low Dividend")

    if y["price"] and y["52w_high"] and y["price"] <= 0.9 * y["52w_high"]:
        score += 1
    else:
        remarks.append("Near 52W High")

    verdict = "BUY" if score >= 5 else "WATCH" if score >= 3 else "AVOID"

    return {
        "Stock": stock,
        "Price": y["price"],
        "Market Cap (₹ Cr)": y["market_cap_cr"],
        "52W High": y["52w_high"],
        "52W Low": y["52w_low"],
        "P/E": y["pe"],
        "Book Value": s["book_value"],
        "ROE": y["roe"],
        "ROCE": s["roce"],
        "Div %": y["div_yield"],
        "Face Value": s["face_value"],
        "Score": score,
        "Verdict": verdict,
        "Remarks": ", ".join(remarks)
    }
