import requests
import yfinance as yf
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}

# -----------------------------
# YAHOO DATA (STABLE + CLEAN)
# -----------------------------
def get_yahoo(stock):
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
        "market_cap_cr": (
            round(info.get("marketCap") / 1e7, 2)
            if info.get("marketCap") else None
        ),
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

# -----------------------------
# SCREENER (ONLY RELIABLE FIELD)
# -----------------------------
def get_screener(stock):
    try:
        soup = BeautifulSoup(
            requests.get(
                f"https://www.screener.in/company/{stock}/",
                headers=HEADERS,
                timeout=10
            ).text,
            "lxml"
        )

        data = {}
        for li in soup.select("li"):
            k = li.find("span", class_="name")
            v = li.find("span", class_="value")
            if k and v:
                data[k.text.strip()] = v.text.strip()

        roce = None
        if data.get("ROCE"):
            roce = float(data["ROCE"].replace("%", "").strip())

        return {
            "roce": roce,
            "face_value": data.get("Face Value")
        }
    except:
        return {
            "roce": None,
            "face_value": None
        }

# -----------------------------
# ANALYSIS + SCORING
# -----------------------------
def analyze(stock):
    if not stock or not stock.strip():
        return None

    stock = stock.strip().upper()

    y = get_yahoo(stock)
    s = get_screener(stock)

    score = 0
    remarks = []

    # ROE
    if y["roe"] and y["roe"] >= 15:
        score += 1
    else:
        remarks.append("Low ROE")

    # ROCE
    if s["roce"] and s["roce"] >= 15:
        score += 1
    else:
        remarks.append("Low ROCE")

    # PE
    if y["pe"] and y["pe"] <= 25:
        score += 1
    else:
        remarks.append("High PE")

    # Debt (ignore if ROCE strong)
    if (y["debt_equity"] is None or y["debt_equity"] <= 1) or (s["roce"] and s["roce"] >= 25):
        score += 1
    else:
        remarks.append("High Debt")

    # Dividend
    if y["div_yield"] and y["div_yield"] >= 1:
        score += 1
    else:
        remarks.append("Low Dividend")

    # Price vs 52W High
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
        "Book Value": y["book_value"],
        "ROE": y["roe"],
        "ROCE": s["roce"],
        "Div %": y["div_yield"],
        "Face Value": s["face_value"],
        "Score": score,
        "Verdict": verdict,
        "Remarks": ", ".join(remarks)
    }
