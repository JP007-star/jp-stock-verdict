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
# YAHOO DATA (SAFE)
# -----------------------------
def get_yahoo(stock):
    try:
        t = yf.Ticker(f"{stock}.NS")
        info = t.info or {}

        raw_div = info.get("dividendYield")
        if raw_div is None:
            div_yield = None
        elif raw_div > 1:
            div_yield = round(raw_div, 2)
        else:
            div_yield = round(raw_div * 100, 2)

        return {
            "price": info.get("currentPrice"),
            "market_cap": info.get("marketCap"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "pe": info.get("trailingPE"),
            "book_value": info.get("bookValue"),
            "roe": (
                round(info.get("returnOnEquity") * 100, 2)
                if info.get("returnOnEquity") else None
            ),
            "div_yield": div_yield,
            "debt_equity": info.get("debtToEquity")
        }
    except Exception as e:
        return {}

# -----------------------------
# SCREENER (SAFE)
# -----------------------------
def get_screener(stock):
    try:
        r = requests.get(
            f"https://www.screener.in/company/{stock}/",
            headers=HEADERS,
            timeout=8
        )
        if r.status_code != 200:
            return {"roce": None, "face_value": None}

        soup = BeautifulSoup(r.text, "lxml")

        data = {}
        for li in soup.select("li"):
            k = li.find("span", class_="name")
            v = li.find("span", class_="value")
            if k and v:
                data[k.text.strip()] = v.text.strip()

        roce = None
        if data.get("ROCE"):
            roce = safe_float(data["ROCE"].replace("%", ""))

        return {
            "roce": roce,
            "face_value": data.get("Face Value")
        }
    except:
        return {"roce": None, "face_value": None}

# -----------------------------
# ANALYSIS (NEVER FAILS)
# -----------------------------
def analyze(stock):
    if not stock or not stock.strip():
        return None

    stock = stock.strip().upper()

    y = get_yahoo(stock)
    s = get_screener(stock)

    score = 0
    remarks = []

    roe = y.get("roe")
    roce = s.get("roce")
    pe = y.get("pe")
    div = y.get("div_yield")
    price = y.get("price")
    high = y.get("52w_high")
    debt = y.get("debt_equity")

    if roe and roe >= 15:
        score += 1
    else:
        remarks.append("Low ROE")

    if roce and roce >= 15:
        score += 1
    else:
        remarks.append("Low ROCE")

    if pe and pe <= 25:
        score += 1
    else:
        remarks.append("High PE")

    if (debt is None or debt <= 1) or (roce and roce >= 25):
        score += 1
    else:
        remarks.append("High Debt")

    if div and div >= 1:
        score += 1
    else:
        remarks.append("Low Dividend")

    if price and high and price <= 0.9 * high:
        score += 1
    else:
        remarks.append("Near 52W High")

    verdict = "BUY" if score >= 5 else "WATCH" if score >= 3 else "AVOID"

    return {
        "Stock": stock,
        "Price": price,
        "52W High": high,
        "52W Low": y.get("52w_low"),
        "P/E": pe,
        "ROE": roe,
        "ROCE": roce,
        "Div %": div,
        "Score": score,
        "Verdict": verdict,
        "Remarks": ", ".join(remarks)
    }
