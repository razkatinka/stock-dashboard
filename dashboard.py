import os
import io
import requests
from datetime import date, datetime, timedelta

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ── FMP config ────────────────────────────────────────────────────────────────
FMP_BASE = "https://financialmodelingprep.com/stable"

# ── Colors ────────────────────────────────────────────────────────────────────
BG_MAIN = "#0D1B2A"
BG_CARD = "#112233"
BG_CHART = "#1a2a3a"
COLOR_GREEN = "#00FF88"
COLOR_RED = "#FF4444"
COLOR_YELLOW = "#FFD700"
COLOR_WHITE = "#FFFFFF"
COLOR_MUTED = "#8899AA"

# ── Peer map ──────────────────────────────────────────────────────────────────
PEER_MAP = {
    "Technology": ["NVDA", "QCOM", "AVGO", "SNPS", "CDNS"],
    "Semiconductors": ["NVDA", "QCOM", "AVGO", "SNPS", "CDNS"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE"],
    "Financial Services": ["JPM", "BAC", "GS", "MS", "C"],
    "Healthcare": ["JNJ", "PFE", "UNH", "ABBV", "MRK"],
    "Communication Services": ["META", "GOOGL", "NFLX", "DIS", "CMCSA"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "Industrials": ["CAT", "HON", "UNP", "GE", "RTX"],
    "Consumer Defensive": ["PG", "KO", "PEP", "WMT", "COST"],
    "Real Estate": ["PLD", "AMT", "CCI", "EQIX", "SPG"],
    "Default": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
}

SECTOR_MEDIANS = {
    "Technology": {"gross": 0.55, "operating": 0.22, "ebitda": 0.28, "fcf": 0.18},
    "Semiconductors": {"gross": 0.52, "operating": 0.20, "ebitda": 0.26, "fcf": 0.16},
    "Consumer Cyclical": {"gross": 0.35, "operating": 0.10, "ebitda": 0.14, "fcf": 0.08},
    "Healthcare": {"gross": 0.58, "operating": 0.16, "ebitda": 0.22, "fcf": 0.12},
    "Financial Services": {"gross": 0.60, "operating": 0.30, "ebitda": 0.35, "fcf": 0.20},
    "Communication Services": {"gross": 0.50, "operating": 0.18, "ebitda": 0.28, "fcf": 0.15},
    "Energy": {"gross": 0.30, "operating": 0.15, "ebitda": 0.25, "fcf": 0.12},
    "Industrials": {"gross": 0.35, "operating": 0.12, "ebitda": 0.18, "fcf": 0.08},
    "Consumer Defensive": {"gross": 0.40, "operating": 0.14, "ebitda": 0.18, "fcf": 0.10},
    "Real Estate": {"gross": 0.65, "operating": 0.35, "ebitda": 0.55, "fcf": 0.25},
    "Default": {"gross": 0.45, "operating": 0.15, "ebitda": 0.20, "fcf": 0.10},
}

INDUSTRY_WACC = {
    "Technology": 0.09, "Semiconductors": 0.09,
    "Consumer Cyclical": 0.08, "Healthcare": 0.08,
    "Financial Services": 0.10, "Communication Services": 0.09,
    "Energy": 0.08, "Industrials": 0.08,
    "Consumer Defensive": 0.07, "Real Estate": 0.07,
    "Default": 0.09,
}

BUSINESS_MODEL_MAP = {
    "Semiconductors": "מוליכים למחצה / IP לייסנסינג",
    "Software—Application": "SaaS / תוכנה כשירות",
    "Software—Infrastructure": "תשתית ענן / DevOps",
    "Technology": "מוצרים + שירותים + ענן",
    "Consumer Electronics": "חומרה + שירותים",
    "Consumer Cyclical": "קמעונאות / צרכנות",
    "Healthcare": "ביוטכנולוגיה / פארמה",
    "Financial Services": "שירותים פיננסיים",
    "Communication Services": "מדיה / תקשורת",
    "Energy": "אנרגיה / דלק וגז",
    "Real Estate": 'נדל"ן / REIT',
    "Industrials": "תעשייה / ייצור",
    "Consumer Defensive": "מוצרי צריכה בסיסיים",
    "Default": "מגוון עסקי",
}

CATALYST_KEYWORDS = [
    "growth", "expand", "innovation", "partnership", "demand", "increase",
    "leading", "advantage", "opportunity", "market share", "launch", "strong",
    "revenue", "record", "acquisition", "license", "royalty", "cloud", "ai",
    "artificial intelligence", "data center", "5g", "electric", "platform",
]
RISK_KEYWORDS = [
    "competition", "regulation", "debt", "concentration", "dependency",
    "litigation", "decline", "uncertainty", "risk", "challenge", "volatile",
    "cyclical", "supply chain", "geopolit", "tariff", "lawsuit", "penalty",
    "inflation", "interest rate", "customer concentration", "single customer",
]

# Map Yahoo-style index tickers to FMP-compatible ETF proxies
_FMP_SYMBOL_MAP = {"^IXIC": "QQQ", "^GSPC": "SPY"}

CHART_DEFAULTS = dict(
    template="plotly_dark",
    paper_bgcolor=BG_MAIN,
    plot_bgcolor=BG_CHART,
    font=dict(family="Heebo, sans-serif", color=COLOR_WHITE, size=11),
    margin=dict(l=40, r=20, t=40, b=40),
    showlegend=False,
)

def _chart_layout(**overrides):
    return {**CHART_DEFAULTS, **overrides}


# ── CSS ───────────────────────────────────────────────────────────────────────
def inject_css() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Heebo', sans-serif !important;
        background-color: #0D1B2A !important;
        color: #FFFFFF !important;
    }
    .stApp { background-color: #0D1B2A !important; }
    [data-testid="stAppViewContainer"] { background-color: #0D1B2A !important; }
    [data-testid="stSidebar"] { background-color: #091520 !important; }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1rem; max-width: 100%; }
    .card {
        background: #112233;
        border: 1px solid #1e3a5f;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }
    .section-header {
        font-size: 1.05rem;
        font-weight: 700;
        color: #00FF88;
        border-bottom: 1px solid #1e3a5f;
        padding-bottom: 5px;
        margin-bottom: 10px;
        direction: rtl;
        text-align: right;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
        font-weight: 700 !important;
        color: #FFFFFF !important;
    }
    [data-testid="stMetricLabel"] {
        color: #8899AA !important;
        font-size: 0.72rem !important;
    }
    .stTabs [data-baseweb="tab"] {
        background: #112233 !important;
        color: #8899AA !important;
        border-radius: 6px 6px 0 0 !important;
        font-weight: 600 !important;
    }
    .stTabs [aria-selected="true"] {
        background: #1e3a5f !important;
        color: #FFFFFF !important;
    }
    .scenario-bull {
        border: 2px solid #00FF88; background: #071a12;
        border-radius: 10px; padding: 14px; text-align: center;
    }
    .scenario-base {
        border: 2px solid #FFD700; background: #1a1607;
        border-radius: 10px; padding: 14px; text-align: center;
    }
    .scenario-bear {
        border: 2px solid #FF4444; background: #1a0707;
        border-radius: 10px; padding: 14px; text-align: center;
    }
    .stDataFrame { background-color: #112233 !important; }
    </style>
    """, unsafe_allow_html=True)


# ── FMP helpers ───────────────────────────────────────────────────────────────
def _fmp_get(endpoint: str, api_key: str):
    """GET from FMP. Returns parsed JSON or None on error."""
    try:
        sep = "&" if "?" in endpoint else "?"
        url = f"{FMP_BASE}/{endpoint}{sep}apikey={api_key}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ── FMP data normalization ────────────────────────────────────────────────────
def _build_history_df(hist_data) -> pd.DataFrame:
    """Convert FMP historical price response to DataFrame with Close column.
    Handles both stable API (returns list) and legacy format (returns {"historical":[...]})."""
    if isinstance(hist_data, dict):
        historical = hist_data.get("historical", [])
    elif isinstance(hist_data, list):
        historical = hist_data
    else:
        historical = []
    if not historical:
        return pd.DataFrame()
    records = [{"date": h["date"], "Close": h["close"]}
               for h in historical if h.get("close") is not None]
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def _filter_ytd(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame()
    ytd_start = pd.Timestamp(datetime.now().year, 1, 1)
    return df[df.index >= ytd_start]


def _build_income_df(statements: list) -> pd.DataFrame:
    """Build yfinance-style income DataFrame (metrics as index, dates as columns)."""
    if not statements:
        return pd.DataFrame()
    metric_map = {
        "Total Revenue":            "revenue",
        "EBIT":                     "operatingIncome",
        "Operating Income":         "operatingIncome",
        "EBITDA":                   "ebitda",
        "Income Tax Expense":       "incomeTaxExpense",
        "Pretax Income":            "incomeBeforeTax",
        "Net Income":               "netIncome",
        "Diluted EPS":              "epsdiluted",
        "Basic EPS":                "eps",
        "Research And Development": "researchAndDevelopmentExpenses",
        "Gross Profit":             "grossProfit",
    }
    cols = {}
    for stmt in statements:
        date_key = stmt.get("date", "")
        cols[date_key] = {metric: stmt.get(fk) for metric, fk in metric_map.items()}
    return pd.DataFrame(cols)  # index=metrics, columns=dates (newest first)


def _build_balance_df(statements: list) -> pd.DataFrame:
    if not statements:
        return pd.DataFrame()
    metric_map = {
        "Total Assets":                  "totalAssets",
        "Total Current Assets":          "totalCurrentAssets",
        "Total Current Liabilities":     "totalCurrentLiabilities",
        "Total Stockholders Equity":     "totalStockholdersEquity",
        "Total Debt":                    "totalDebt",
        "Cash And Short Term Investments": "cashAndShortTermInvestments",
    }
    cols = {}
    for stmt in statements:
        date_key = stmt.get("date", "")
        cols[date_key] = {metric: stmt.get(fk) for metric, fk in metric_map.items()}
    return pd.DataFrame(cols)


def _build_cashflow_df(statements: list) -> pd.DataFrame:
    if not statements:
        return pd.DataFrame()
    metric_map = {
        "Repurchase Of Capital Stock": "commonStockRepurchased",
        "Common Stock Repurchased":    "commonStockRepurchased",
        "Cash Dividends Paid":         "dividendsPaid",
        "Common Stock Dividend Paid":  "dividendsPaid",
        "Free Cash Flow":              "freeCashFlow",
        "Operating Cash Flow":         "operatingCashFlow",
    }
    cols = {}
    for stmt in statements:
        date_key = stmt.get("date", "")
        cols[date_key] = {metric: stmt.get(fk) for metric, fk in metric_map.items()}
    return pd.DataFrame(cols)


def _build_institutional_df(holders: list, current_price) -> pd.DataFrame:
    if not holders:
        return pd.DataFrame()
    rows = []
    for h in holders[:10]:
        shares = h.get("shares") or 0
        price = current_price or 0
        value = float(shares) * float(price) if shares and price else None
        # FMP changePercent is in % units (e.g. 0.14 = 0.14%), divide by 100 for decimal
        pct = h.get("changePercent")
        rows.append({
            "Holder":    h.get("holder", ""),
            "Value":     value,
            "% Out":     None,
            "pctChange": float(pct) / 100 if pct is not None else None,
        })
    return pd.DataFrame(rows)


def _build_recs_df(analyst_recs: list) -> pd.DataFrame:
    """Convert FMP analyst-stock-recommendations to yfinance-style DataFrame."""
    if not analyst_recs:
        return pd.DataFrame()
    rows = []
    for i, rec in enumerate(analyst_recs[:4]):
        rows.append({
            "period":    f"{-i}m",
            "strongBuy": rec.get("analystRatingsStrongBuy", 0) or 0,
            "buy":       rec.get("analystRatingsbuy", 0) or rec.get("analystRatingsBuy", 0) or 0,
            "hold":      rec.get("analystRatingsHold", 0) or 0,
            "sell":      rec.get("analystRatingsSell", 0) or 0,
            "strongSell":rec.get("analystRatingsStrongSell", 0) or 0,
        })
    return pd.DataFrame(rows)


def _build_apt(price_targets_raw: list) -> dict:
    """Aggregate individual FMP price targets into mean/high/low dict."""
    if not price_targets_raw:
        return {}
    targets = [float(x["priceTarget"]) for x in price_targets_raw if x.get("priceTarget")]
    if not targets:
        return {}
    return {
        "mean":    round(sum(targets) / len(targets), 2),
        "high":    max(targets),
        "low":     min(targets),
        "current": targets[0],
    }


def _normalize_info(profile, income_annual, balance, cashflow,
                    key_metrics, ratios, estimates, history_df) -> dict:
    """Build yfinance-compatible info dict from FMP API responses."""
    if not profile:
        return {}
    p  = profile[0]
    ia = income_annual[0] if income_annual else {}
    bl = balance[0]       if balance       else {}
    cf = cashflow[0]      if cashflow      else {}
    km = key_metrics[0]   if key_metrics   else {}
    ra = ratios[0]        if ratios        else {}
    est = estimates[0]    if estimates     else {}

    # ── Compute from history ──────────────────────────────────────────────────
    w52_high = w52_low = w52_chg = ma50 = ma200 = None
    if history_df is not None and len(history_df) > 0:
        closes = history_df["Close"].dropna()
        if len(closes) > 0:
            w52_high = float(closes.max())
            w52_low  = float(closes.min())
            if len(closes) > 1:
                w52_chg = float(closes.iloc[-1]) / float(closes.iloc[0]) - 1
        if len(closes) >= 50:
            ma50  = float(closes.iloc[-50:].mean())
        if len(closes) >= 200:
            ma200 = float(closes.iloc[-200:].mean())

    # ── Forward P/E: price / forward EPS estimate ────────────────────────────
    price   = p.get("price")
    fwd_eps = est.get("estimatedEpsAvg")
    fwd_pe  = None
    if price and fwd_eps and float(fwd_eps) > 0:
        fwd_pe = float(price) / float(fwd_eps)
    elif km.get("peRatio"):
        fwd_pe = km["peRatio"]  # trailing as fallback

    # ── Revenue / earnings growth (YoY from annual statements) ───────────────
    rev_growth = earn_growth = None
    if len(income_annual) >= 2:
        r0, r1 = income_annual[0].get("revenue") or 0, income_annual[1].get("revenue") or 0
        if r1:
            rev_growth = (r0 - r1) / abs(r1)
        e0, e1 = income_annual[0].get("netIncome") or 0, income_annual[1].get("netIncome") or 0
        if e1:
            earn_growth = (e0 - e1) / abs(e1)

    # ── Debt/Equity × 100 to match yfinance convention ───────────────────────
    total_debt = float(bl.get("totalDebt") or 0)
    equity     = float(bl.get("totalStockholdersEquity") or 1)
    de_ratio   = (total_debt / equity) * 100 if equity else None

    return {
        "symbol":                       p.get("symbol", ""),
        "longName":                     p.get("companyName", ""),
        "sector":                       p.get("sector", "Default") or "Default",
        "industry":                     p.get("industry", "") or "",
        "fullExchangeName":             p.get("exchange", "") or "",
        "longBusinessSummary":          p.get("description", "") or "",
        "currentPrice":                 price,
        "regularMarketPrice":           price,
        "marketCap":                    p.get("mktCap"),
        "beta":                         p.get("beta"),
        "52WeekChange":                 w52_chg,
        "fiftyTwoWeekHigh":             w52_high,
        "fiftyTwoWeekLow":              w52_low,
        "fiftyDayAverage":              ma50,
        "twoHundredDayAverage":         ma200,
        "totalRevenue":                 ia.get("revenue"),
        "grossMargins":                 ia.get("grossProfitRatio"),
        "operatingMargins":             ia.get("operatingIncomeRatio"),
        "ebitdaMargins":                ia.get("ebitdaratio"),
        "profitMargins":                ia.get("netIncomeRatio"),
        "freeCashflow":                 cf.get("freeCashFlow"),
        "totalCash":                    bl.get("cashAndShortTermInvestments"),
        "debtToEquity":                 de_ratio,
        "currentRatio":                 ra.get("currentRatio") or km.get("currentRatio"),
        "returnOnEquity":               ra.get("returnOnEquity"),
        "forwardPE":                    fwd_pe,
        "forwardEps":                   fwd_eps,
        "trailingPE":                   km.get("peRatio"),
        "priceToBook":                  km.get("pbRatio") or ra.get("priceToBookRatio"),
        "priceToSalesTrailing12Months": km.get("priceToSalesRatio") or ra.get("priceToSalesRatio"),
        "enterpriseToEbitda":           km.get("enterpriseValueOverEBITDA"),
        "pegRatio":                     ra.get("priceEarningsToGrowthRatio"),
        "earningsGrowth":               earn_growth,
        "revenueGrowth":                rev_growth,
        "numberOfAnalystOpinions":      est.get("numberAnalystsEstimatedEps"),
    }


# ── Data layer (FMP) ──────────────────────────────────────────────────────────
def debug_fmp_connection() -> None:
    """Run outside @st.cache_data so st.* calls actually render."""
    api_key = os.environ.get("FMP_API_KEY", "")
    key_preview = (api_key[:4] + "…") if len(api_key) >= 4 else f"(empty, len={len(api_key)})"
    st.info(f"🐛 FMP_API_KEY starts with: `{key_preview}`")
    try:
        url  = f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={api_key}"
        resp = requests.get(url, timeout=15)
        st.warning(f"🐛 FMP /profile/AAPL → HTTP {resp.status_code}")
        st.code(resp.text[:2000], language="json")
    except Exception as err:
        st.error(f"🐛 requests.get failed: {type(err).__name__}: {err}")


@st.cache_data(ttl=3600)
def fetch_ticker_data(ticker: str) -> dict:
    api_key = os.environ.get("FMP_API_KEY", "")
    t = ticker.upper()
    one_year_ago = (date.today() - timedelta(days=365)).isoformat()

    def get(endpoint):
        return _fmp_get(endpoint, api_key)

    # ── Fetch all endpoints (stable API: query-param style) ──────────────────
    profile_data  = get(f"profile?symbol={t}")                                             or []
    income_annual = get(f"income-statement?symbol={t}&period=annual&limit=4")             or []
    income_qtrly  = get(f"income-statement?symbol={t}&period=quarter&limit=8")            or []
    balance       = get(f"balance-sheet-statement?symbol={t}&period=annual&limit=4")      or []
    cashflow      = get(f"cash-flow-statement?symbol={t}&period=annual&limit=4")          or []
    key_metrics   = get(f"key-metrics?symbol={t}&period=annual&limit=1")                  or []
    ratios        = get(f"ratios?symbol={t}&period=annual&limit=1")                       or []
    estimates     = get(f"analyst-estimates?symbol={t}&limit=2")                          or []
    price_tgts    = get(f"price-target?symbol={t}&limit=20")                              or []
    institutional = get(f"institutional-holder?symbol={t}")                                or []
    analyst_recs  = get(f"analyst-stock-recommendations?symbol={t}&limit=4")              or []
    hist_raw      = get(f"historical-price-eod?symbol={t}&from={one_year_ago}")           or []

    # ── Build DataFrames ──────────────────────────────────────────────────────
    history_1y  = _build_history_df(hist_raw)
    history_ytd = _filter_ytd(history_1y)
    info        = _normalize_info(profile_data, income_annual, balance, cashflow,
                                  key_metrics, ratios, estimates, history_1y)

    return {
        "info":                  info,
        "financials":            _build_income_df(income_annual),
        "quarterly_financials":  _build_income_df(income_qtrly),
        "balance_sheet":         _build_balance_df(balance),
        "cashflow":              _build_cashflow_df(cashflow),
        "history":               history_1y,
        "history_ytd":           history_ytd,
        "institutional_holders": _build_institutional_df(institutional, info.get("currentPrice")),
        "recommendations":       _build_recs_df(analyst_recs),
        "analyst_price_targets": _build_apt(price_tgts),
    }


@st.cache_data(ttl=3600)
def fetch_peer_data(peers: tuple) -> dict:
    api_key = os.environ.get("FMP_API_KEY", "")
    result = {}
    for p in peers:
        try:
            profile = _fmp_get(f"profile?symbol={p}", api_key)                      or []
            km      = _fmp_get(f"key-metrics?symbol={p}&period=annual&limit=1", api_key) or []
            ra      = _fmp_get(f"ratios?symbol={p}&period=annual&limit=1", api_key)      or []
            pinfo: dict = {}
            if profile:
                pr = profile[0]
                pinfo["symbol"]    = pr.get("symbol")
                pinfo["longName"]  = pr.get("companyName")
                pinfo["sector"]    = pr.get("sector")
                pinfo["industry"]  = pr.get("industry")
                pinfo["marketCap"] = pr.get("mktCap")
                pinfo["beta"]      = pr.get("beta")
            if km:
                k = km[0]
                pinfo["forwardPE"]                      = k.get("peRatio")
                pinfo["enterpriseToEbitda"]             = k.get("enterpriseValueOverEBITDA")
                pinfo["priceToSalesTrailing12Months"]   = k.get("priceToSalesRatio")
                pinfo["priceToBook"]                    = k.get("pbRatio")
                pinfo["currentRatio"]                   = k.get("currentRatio")
            if ra:
                r = ra[0]
                pinfo.setdefault("priceToBook",                  r.get("priceToBookRatio"))
                pinfo.setdefault("priceToSalesTrailing12Months", r.get("priceToSalesRatio"))
                pinfo["returnOnEquity"] = r.get("returnOnEquity")
                pinfo.setdefault("currentRatio", r.get("currentRatio"))
            result[p] = pinfo
        except Exception:
            result[p] = {}
    return result


@st.cache_data(ttl=3600)
def fetch_ytd_history(tickers: tuple) -> dict:
    api_key   = os.environ.get("FMP_API_KEY", "")
    ytd_start = date(date.today().year, 1, 1).isoformat()
    result    = {}
    for t in tickers:
        try:
            fmp_sym = _FMP_SYMBOL_MAP.get(t, t)
            raw     = _fmp_get(f"historical-price-eod?symbol={fmp_sym}&from={ytd_start}", api_key)
            df      = _build_history_df(raw or [])
            if df is not None and len(df) > 1:
                result[t] = df["Close"]     # keyed by original ticker (^IXIC etc.)
        except Exception:
            pass
    return result


# ── Technical indicators ──────────────────────────────────────────────────────
def calc_rsi(close: pd.Series, period: int = 14) -> float:
    if len(close) < period + 1:
        return float("nan")
    delta    = close.diff().dropna()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    last_loss = float(avg_loss.iloc[-1])
    if last_loss == 0:
        return 100.0
    rs = float(avg_gain.iloc[-1]) / last_loss
    return round(100 - (100 / (1 + rs)), 2)


def calc_macd(close: pd.Series) -> dict:
    if len(close) < 26:
        return {"label": "N/A", "macd": float("nan"), "signal": float("nan")}
    ema12          = close.ewm(span=12, adjust=False).mean()
    ema26          = close.ewm(span=26, adjust=False).mean()
    macd           = ema12 - ema26
    signal         = macd.ewm(span=9, adjust=False).mean()
    latest_macd    = float(macd.iloc[-1])
    latest_signal  = float(signal.iloc[-1])
    return {
        "macd":      round(latest_macd, 3),
        "signal":    round(latest_signal, 3),
        "histogram": round(float((macd - signal).iloc[-1]), 3),
        "label":     "BULLISH" if latest_macd > latest_signal else "BEARISH",
    }


def calc_fibonacci_levels(high: float, low: float) -> dict:
    if not high or not low or high <= low:
        return {}
    diff = high - low
    return {
        "ATH / 52W High": high,
        "Fib 78.6%":      low + diff * 0.786,
        "Fib 61.8%":      low + diff * 0.618,
        "Fib 50.0%":      low + diff * 0.500,
        "Fib 38.2%":      low + diff * 0.382,
        "Fib 23.6%":      low + diff * 0.236,
        "52W Low":        low,
    }


def calc_roic(financials: pd.DataFrame, balance_sheet: pd.DataFrame) -> float:
    try:
        ebit_row = next((r for r in ["EBIT", "Operating Income"] if r in financials.index), None)
        if not ebit_row:
            return float("nan")
        ebit = float(financials.loc[ebit_row].iloc[0])
        tax  = 0.21
        if "Income Tax Expense" in financials.index and "Pretax Income" in financials.index:
            pretax  = float(financials.loc["Pretax Income"].iloc[0])
            tax_exp = float(financials.loc["Income Tax Expense"].iloc[0])
            if pretax != 0:
                tax = tax_exp / pretax
        ic_row = next((r for r in ["Total Assets"] if r in balance_sheet.index), None)
        if not ic_row:
            return float("nan")
        ic = float(balance_sheet.loc[ic_row].iloc[0])
        if ic == 0:
            return float("nan")
        return round((ebit * (1 - tax)) / ic * 100, 2)
    except Exception:
        return float("nan")


def calc_quality_scores(info: dict, fin: pd.DataFrame, bs: pd.DataFrame) -> dict:
    def clamp(val):
        return max(0.0, min(10.0, float(val)))
    eg       = safe_get(info, "earningsGrowth") or 0
    rg       = safe_get(info, "revenueGrowth")  or 0
    growth   = clamp(((eg + rg) / 2) * 40 + 5)
    peg      = safe_get(info, "pegRatio", 2) or 2
    if peg < 0:
        peg = 3
    value    = clamp(10 - min(peg * 2, 10))
    w52      = safe_get(info, "52WeekChange", 0) or 0
    momentum = clamp(w52 * 15 + 5)
    pm       = safe_get(info, "profitMargins", 0) or 0
    roe      = safe_get(info, "returnOnEquity", 0) or 0
    quality  = clamp(pm * 20 + min(max(roe, 0), 1) * 5)
    return {
        "צמיחה":   round(growth, 1),
        "ערך":     round(value, 1),
        "מומנטום": round(momentum, 1),
        "איכות":   round(quality, 1),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_get(d: dict, key: str, default=None):
    if not d:
        return default
    val = d.get(key, default)
    return val if val is not None else default


def fmt_currency(val, suffix="B") -> str:
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if np.isnan(v):
            return "N/A"
        if suffix == "B":
            return f"${v / 1e9:.2f}B"
        if suffix == "M":
            return f"${v / 1e6:.0f}M"
        return f"${v:,.2f}"
    except Exception:
        return "N/A"


def fmt_pct(val) -> str:
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if np.isnan(v):
            return "N/A"
        return f"{v * 100:.1f}%"
    except Exception:
        return "N/A"


def fmt_num(val, decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if np.isnan(v):
            return "N/A"
        return f"{v:.{decimals}f}"
    except Exception:
        return "N/A"


def rtl_header(text: str) -> None:
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)


def get_peers(sector: str, industry: str = "") -> list:
    return PEER_MAP.get(industry) or PEER_MAP.get(sector) or PEER_MAP["Default"]


def get_sector_medians(sector: str) -> dict:
    return SECTOR_MEDIANS.get(sector, SECTOR_MEDIANS["Default"])


def infer_business_model(info: dict) -> str:
    industry = (info.get("industry") or "")
    sector   = (info.get("sector")   or "")
    for key, val in BUSINESS_MODEL_MAP.items():
        if key in industry or key in sector:
            return val
    return BUSINESS_MODEL_MAP["Default"]


def extract_business_bullets(summary: str) -> list:
    if not summary:
        return ["N/A", "N/A", "N/A"]
    sentences = [s.strip() + "." for s in summary.split(". ") if len(s.strip()) > 25]
    bullets = sentences[:3]
    while len(bullets) < 3:
        bullets.append("—")
    return bullets


def extract_catalysts_risks(summary: str, sector: str = "Default") -> tuple:
    if not summary:
        summary = ""
    sentences = [s.strip() for s in summary.replace(". ", ".|").split("|") if len(s.strip()) > 15]
    pos_sentences, neg_sentences = [], []
    for s in sentences:
        s_lower = s.lower()
        pos_score = sum(1 for kw in CATALYST_KEYWORDS if kw in s_lower)
        neg_score = sum(1 for kw in RISK_KEYWORDS     if kw in s_lower)
        if pos_score > neg_score and pos_score > 0:
            pos_sentences.append(s)
        elif neg_score > pos_score and neg_score > 0:
            neg_sentences.append(s)
    sector_catalysts = {
        "Technology":     ["מנהיגות AI וחדשנות טכנולוגית", "הרחבת נוכחות בענן ו-SaaS", "שוק addressable גדל"],
        "Semiconductors": ["ביקוש גובר לשבבים ו-AI", "הרחבת לייסנסינג ו-IP royalties", "צמיחה בסגמנט מרכזי הנתונים"],
        "Consumer Cyclical": ["גידול בצריכה הפרטית", "הרחבה לשווקים חדשים", "חדשנות במוצרים ושירותים"],
        "Default":        ["צמיחה בהכנסות ובשיתופי פעולה", "הרחבת נתח שוק", "פיתוח מוצרים ושירותים חדשים"],
    }
    sector_risks = {
        "Technology":     ["תחרות גוברת מחברות טכנולוגיה גדולות", "רגולציה ואנטיטראסט", "תלות בשרשרת אספקה גלובלית"],
        "Semiconductors": ["תלות בלקוח/שוק יחיד", "מחזוריות ענף השבבים", "סיכונים גיאופוליטיים בייצור"],
        "Consumer Cyclical": ["רגישות למצב המאקרו כלכלי", "תחרות מחיר מענקיות קמעונאות", "שינויים בהרגלי הצריכה"],
        "Default":        ["תחרות גוברת בשוק הגלובלי", "סיכוני מאקרו וריביות", "חשיפה גיאופוליטית ושרשרת אספקה"],
    }
    def shorten(s: str) -> str:
        return s[:110] + "..." if len(s) > 110 else s
    cats  = [shorten(s) for s in pos_sentences[:3]]
    risks = [shorten(s) for s in neg_sentences[:3]]
    fb_cats  = sector_catalysts.get(sector, sector_catalysts["Default"])
    fb_risks = sector_risks.get(sector, sector_risks["Default"])
    while len(cats)  < 3: cats.append(fb_cats[len(cats) % len(fb_cats)])
    while len(risks) < 3: risks.append(fb_risks[len(risks) % len(fb_risks)])
    return cats[:3], risks[:3]


# ── Charts ────────────────────────────────────────────────────────────────────
def chart_quarterly_revenue(qfin: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    revenue_row = None
    for label in ["Total Revenue", "Revenue", "Net Revenue"]:
        if label in qfin.index:
            revenue_row = qfin.loc[label]
            break
    if revenue_row is not None:
        row    = revenue_row.iloc[:8][::-1].dropna()
        dates  = [str(c)[:7] for c in row.index]
        vals   = [float(v) / 1e6 for v in row.values]
        colors = [COLOR_GREEN if i == len(vals) - 1 else "#3a7aff" for i in range(len(vals))]
        fig.add_trace(go.Bar(
            x=dates, y=vals, marker_color=colors,
            text=[f"${v:.0f}M" for v in vals],
            textposition="outside", textfont=dict(size=9, color=COLOR_WHITE),
        ))
    fig.update_layout(
        **CHART_DEFAULTS,
        title=dict(text="Quarterly Revenue ($M)", font=dict(size=12, color=COLOR_GREEN)),
        height=280,
        yaxis=dict(gridcolor="#1e3a5f"),
        xaxis=dict(gridcolor="#1e3a5f"),
    )
    return fig


def chart_margins_vs_sector(info: dict, medians: dict) -> go.Figure:
    fcf     = safe_get(info, "freeCashflow") or 0
    rev     = safe_get(info, "totalRevenue") or 1
    company = [
        (safe_get(info, "grossMargins")    or 0) * 100,
        (safe_get(info, "operatingMargins") or 0) * 100,
        (safe_get(info, "ebitdaMargins")   or 0) * 100,
        (fcf / rev) * 100,
    ]
    sector = [medians[k] * 100 for k in ["gross", "operating", "ebitda", "fcf"]]
    labels = ["Gross", "Operating", "EBITDA", "FCF"]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=labels, x=company, orientation="h", name="Company",
                         marker_color=COLOR_GREEN, opacity=0.85,
                         text=[f"{v:.1f}%" for v in company], textposition="outside"))
    fig.add_trace(go.Bar(y=labels, x=sector, orientation="h", name="Sector Median",
                         marker_color="#3a7aff", opacity=0.6,
                         text=[f"{v:.1f}%" for v in sector], textposition="outside"))
    fig.update_layout(
        **_chart_layout(showlegend=True),
        barmode="group",
        title=dict(text="Margins vs Sector Median (%)", font=dict(size=12, color=COLOR_GREEN)),
        height=280,
        legend=dict(orientation="h", y=-0.25, font=dict(size=10)),
        yaxis=dict(gridcolor="#1e3a5f"),
        xaxis=dict(gridcolor="#1e3a5f"),
    )
    return fig


def chart_eps_progression(financials: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    eps_row = None
    for label in ["Diluted EPS", "Basic EPS", "EPS"]:
        if label in financials.index:
            eps_row = financials.loc[label]
            break
    if eps_row is not None:
        row   = eps_row[::-1].dropna()
        dates = [str(c)[:7] for c in row.index]
        vals  = [float(v) for v in row.values]
        colors = [COLOR_GREEN if v >= 0 else COLOR_RED for v in vals]
        fig.add_trace(go.Scatter(
            x=dates, y=vals, mode="lines+markers+text",
            line=dict(color=COLOR_GREEN, width=2),
            marker=dict(color=colors, size=8),
            text=[f"${v:.2f}" for v in vals],
            textposition="top center", textfont=dict(size=9),
        ))
    fig.update_layout(
        **CHART_DEFAULTS,
        title=dict(text="Annual EPS (Diluted)", font=dict(size=12, color=COLOR_GREEN)),
        height=200,
        yaxis=dict(gridcolor="#1e3a5f"),
        xaxis=dict(gridcolor="#1e3a5f"),
    )
    return fig


def chart_peer_forward_pe(main_ticker: str, main_info: dict, peer_data: dict) -> go.Figure:
    tickers = [main_ticker] + list(peer_data.keys())
    pe_vals = [safe_get(main_info, "forwardPE")] + [safe_get(v, "forwardPE") for v in peer_data.values()]
    valid   = [(t, v) for t, v in zip(tickers, pe_vals) if v and float(v) > 0]
    if not valid:
        return go.Figure()
    valid.sort(key=lambda x: float(x[1]), reverse=True)
    t_names, t_vals = zip(*valid)
    colors = [COLOR_GREEN if t == main_ticker else "#3a7aff" for t in t_names]
    fig = go.Figure(go.Bar(
        x=[float(v) for v in t_vals], y=list(t_names),
        orientation="h", marker_color=colors,
        text=[f"{float(v):.1f}x" for v in t_vals],
        textposition="outside", textfont=dict(size=10),
    ))
    fig.update_layout(
        **CHART_DEFAULTS,
        title=dict(text="Forward P/E — Peer Comparison", font=dict(size=12, color=COLOR_GREEN)),
        height=280, xaxis_title="Forward P/E",
        yaxis=dict(gridcolor="#1e3a5f"),
        xaxis=dict(gridcolor="#1e3a5f"),
    )
    return fig


def chart_ytd_performance(main_ticker: str, peers: list, ytd_histories: dict) -> go.Figure:
    all_tickers = [main_ticker] + peers + ["^IXIC", "^GSPC"]
    labels_map  = {"^IXIC": "NASDAQ (QQQ)", "^GSPC": "S&P 500 (SPY)"}
    results = []
    for t in all_tickers:
        h = ytd_histories.get(t)
        if h is not None and len(h) >= 2:
            ret = (float(h.iloc[-1]) / float(h.iloc[0]) - 1) * 100
            results.append((labels_map.get(t, t), round(ret, 2)))
    if not results:
        return go.Figure()
    results.sort(key=lambda x: x[1])
    names, rets = zip(*results)
    colors = [COLOR_GREEN if r >= 0 else COLOR_RED for r in rets]
    fig = go.Figure(go.Bar(
        x=list(rets), y=list(names), orientation="h", marker_color=colors,
        text=[f"{r:+.1f}%" for r in rets],
        textposition="outside", textfont=dict(size=10),
    ))
    fig.add_vline(x=0, line_color=COLOR_MUTED, line_width=1, line_dash="dash")
    fig.update_layout(
        **CHART_DEFAULTS,
        title=dict(text="YTD Performance vs Peers & Indices", font=dict(size=12, color=COLOR_GREEN)),
        height=350, xaxis_title="YTD Return (%)",
        yaxis=dict(gridcolor="#1e3a5f"),
        xaxis=dict(gridcolor="#1e3a5f"),
    )
    return fig


def chart_analyst_ratings(recommendations: pd.DataFrame) -> go.Figure:
    if recommendations is None or len(recommendations) == 0:
        return go.Figure()
    row = None
    if "period" in recommendations.columns:
        p0  = recommendations[recommendations["period"] == "0m"]
        row = p0.iloc[0] if len(p0) > 0 else recommendations.iloc[0]
    else:
        row = recommendations.iloc[0]
    col_map = ["strongBuy", "buy", "hold", "sell", "strongSell"]
    labels  = ["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]
    values  = []
    for c in col_map:
        try:
            values.append(int(row[c]) if c in row.index else 0)
        except Exception:
            values.append(0)
    if sum(values) == 0:
        return go.Figure()
    colors = [COLOR_GREEN, "#00cc66", COLOR_YELLOW, "#ff8844", COLOR_RED]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color=BG_MAIN, width=2)),
        hole=0.45, textfont=dict(size=10), textinfo="label+percent",
    ))
    fig.update_layout(
        **_chart_layout(showlegend=True),
        title=dict(text="Analyst Ratings Distribution", font=dict(size=12, color=COLOR_GREEN)),
        height=300,
        legend=dict(orientation="v", x=1.02, y=0.5, font=dict(size=9)),
    )
    return fig


# ── Excel export ──────────────────────────────────────────────────────────────
def build_excel_export(ticker: str, data: dict, peer_data: dict) -> bytes:
    info     = data.get("info", {})
    hist     = data.get("history", pd.DataFrame())
    close    = hist["Close"] if hist is not None and len(hist) > 0 else pd.Series(dtype=float)
    rsi_val  = calc_rsi(close)  if len(close) > 14 else float("nan")
    macd_d   = calc_macd(close) if len(close) > 26 else {}
    apt      = data.get("analyst_price_targets", {})

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        fund_rows = {
            "Metric": ["Last Price", "52W Return", "FY Revenue", "Forward EPS", "Market Cap",
                       "Forward P/E", "EV/EBITDA", "P/S", "P/B", "ROE",
                       "Gross Margin", "Operating Margin", "FCF", "Cash", "Debt/Equity", "Current Ratio"],
            "Value":  [
                safe_get(info, "currentPrice"),
                fmt_pct(safe_get(info, "52WeekChange")),
                fmt_currency(safe_get(info, "totalRevenue"), "B"),
                safe_get(info, "forwardEps"),
                fmt_currency(safe_get(info, "marketCap"), "B"),
                safe_get(info, "forwardPE"),
                safe_get(info, "enterpriseToEbitda"),
                safe_get(info, "priceToSalesTrailing12Months"),
                safe_get(info, "priceToBook"),
                fmt_pct(safe_get(info, "returnOnEquity")),
                fmt_pct(safe_get(info, "grossMargins")),
                fmt_pct(safe_get(info, "operatingMargins")),
                fmt_currency(safe_get(info, "freeCashflow"), "B"),
                fmt_currency(safe_get(info, "totalCash"), "B"),
                fmt_num((safe_get(info, "debtToEquity") or 0) / 100),
                fmt_num(safe_get(info, "currentRatio")),
            ],
        }
        pd.DataFrame(fund_rows).to_excel(writer, sheet_name="Fundamentals", index=False)

        peer_rows = []
        for t, pinfo in {ticker: info, **peer_data}.items():
            peer_rows.append({
                "Ticker":    t,
                "Fwd P/E":   fmt_num(safe_get(pinfo, "forwardPE")),
                "EV/EBITDA": fmt_num(safe_get(pinfo, "enterpriseToEbitda")),
                "P/S":       fmt_num(safe_get(pinfo, "priceToSalesTrailing12Months")),
                "P/B":       fmt_num(safe_get(pinfo, "priceToBook")),
                "ROE":       fmt_pct(safe_get(pinfo, "returnOnEquity")),
            })
        pd.DataFrame(peer_rows).to_excel(writer, sheet_name="Peer Comparison", index=False)

        tech_rows = {
            "Metric": ["Beta", "RSI 14D", "MACD Signal", "50DMA", "200DMA",
                       "52W High", "52W Low", "Analyst Target Mean", "Analyst Target High", "Analyst Target Low"],
            "Value":  [
                safe_get(info, "beta"),
                fmt_num(rsi_val),
                macd_d.get("label", "N/A"),
                safe_get(info, "fiftyDayAverage"),
                safe_get(info, "twoHundredDayAverage"),
                safe_get(info, "fiftyTwoWeekHigh"),
                safe_get(info, "fiftyTwoWeekLow"),
                apt.get("mean") if isinstance(apt, dict) else None,
                apt.get("high") if isinstance(apt, dict) else None,
                apt.get("low")  if isinstance(apt, dict) else None,
            ],
        }
        pd.DataFrame(tech_rows).to_excel(writer, sheet_name="Technical", index=False)
    return output.getvalue()


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar() -> tuple:
    with st.sidebar:
        st.markdown(
            f'<div style="color:{COLOR_GREEN}; font-size:1.25rem; font-weight:700; '
            f'margin-bottom:12px; direction:rtl;">📊 מנתח מניות</div>',
            unsafe_allow_html=True,
        )
        ticker_input = st.text_input(
            "סימול מניה",
            value=st.session_state.get("last_ticker", "AAPL"),
            placeholder="e.g. NVDA, AAPL, ARM",
        ).strip().upper()
        analyze_btn = st.button("🔍 Analyze", use_container_width=True, type="primary")

        st.markdown("---")
        if "last_updated" in st.session_state:
            st.markdown(
                f'<div style="color:{COLOR_MUTED}; font-size:0.75rem; direction:rtl;">'
                f'עודכן: {st.session_state["last_updated"]}</div>',
                unsafe_allow_html=True,
            )
        if "export_data" in st.session_state:
            st.download_button(
                label="📥 Export to Excel",
                data=st.session_state["export_data"],
                file_name=f"{st.session_state.get('last_ticker', 'stock')}_analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    return ticker_input, analyze_btn


# ── Page 1: Fundamentals ──────────────────────────────────────────────────────
def render_fundamentals(ticker: str, data: dict) -> None:
    info = data.get("info", {})
    fin  = data.get("financials", pd.DataFrame())
    qfin = data.get("quarterly_financials", pd.DataFrame())
    bs   = data.get("balance_sheet", pd.DataFrame())
    cf   = data.get("cashflow", pd.DataFrame())

    sector   = safe_get(info, "sector",   "Default") or "Default"
    industry = safe_get(info, "industry", "")        or ""
    peers    = get_peers(sector, industry)
    medians  = get_sector_medians(sector)
    wacc     = INDUSTRY_WACC.get(sector, INDUSTRY_WACC["Default"])

    long_name = safe_get(info, "longName", ticker) or ticker
    exchange  = safe_get(info, "fullExchangeName", "") or ""
    st.markdown(
        f'<h2 style="color:{COLOR_WHITE}; direction:rtl; text-align:right; margin-bottom:8px;">'
        f'{long_name} | {ticker} | {exchange}</h2>',
        unsafe_allow_html=True,
    )

    # KPI row
    try:
        price   = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice")
        w52_chg = safe_get(info, "52WeekChange")
        revenue = safe_get(info, "totalRevenue")
        fwd_eps = safe_get(info, "forwardEps")
        mktcap  = safe_get(info, "marketCap")
        fwd_pe  = safe_get(info, "forwardPE")

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1: st.metric("מחיר אחרון",  f"${price:.2f}" if price else "N/A")
        with c2: st.metric("תשואה 52W",   fmt_pct(w52_chg))
        with c3: st.metric("הכנסות FY",   fmt_currency(revenue, "B"))
        with c4: st.metric("Non-GAAP EPS", f"${fwd_eps:.2f}" if fwd_eps else "N/A")
        with c5: st.metric("שווי שוק",    fmt_currency(mktcap, "B"))
        with c6: st.metric("Forward P/E", f"{float(fwd_pe):.1f}x" if fwd_pe else "N/A")
    except Exception as e:
        st.warning(f"שגיאה ב-KPIs: {e}")

    st.markdown("---")

    # Section 1: עסקים
    rtl_header("1. עסקים")
    try:
        col_biz, col_model = st.columns([2, 1])
        summary = safe_get(info, "longBusinessSummary", "") or ""
        bullets = extract_business_bullets(summary)
        with col_biz:
            for b in bullets:
                st.markdown(
                    f'<div dir="rtl" style="margin-bottom:8px; color:{COLOR_WHITE}; font-size:0.88rem;">• {b}</div>',
                    unsafe_allow_html=True,
                )
        with col_model:
            model_text = infer_business_model(info)
            st.markdown(
                f'<div class="card" style="text-align:center;">'
                f'<div style="color:{COLOR_MUTED}; font-size:0.72rem; direction:rtl;">מודל עסקי</div>'
                f'<div style="color:{COLOR_GREEN}; font-size:0.95rem; font-weight:600; margin-top:8px; direction:rtl;">{model_text}</div>'
                f'<div style="color:{COLOR_MUTED}; font-size:0.72rem; margin-top:10px;">{sector}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    except Exception as e:
        st.warning(f"שגיאה בסעיף עסקים: {e}")

    # Section 2: הכנסות ושוליים
    rtl_header("2. הכנסות ושוליים")
    try:
        col_rev, col_margins = st.columns(2)
        with col_rev:
            if qfin is not None and len(qfin) > 0:
                st.plotly_chart(chart_quarterly_revenue(qfin), use_container_width=True)
            else:
                st.info("אין נתוני הכנסות רבעוניים")
        with col_margins:
            st.plotly_chart(chart_margins_vs_sector(info, medians), use_container_width=True)
        if fin is not None and len(fin) > 0:
            st.plotly_chart(chart_eps_progression(fin), use_container_width=True)
    except Exception as e:
        st.warning(f"שגיאה בסעיף הכנסות: {e}")

    # Section 3: הערכת שווי
    rtl_header("3. הערכת שווי vs. עמיתים")
    peer_data = {}
    try:
        with st.spinner("טוען נתוני עמיתים..."):
            peer_data = fetch_peer_data(tuple(peers))

        col_table, col_chart = st.columns(2)
        with col_table:
            rows = []
            for t, pinfo in {ticker: info, **peer_data}.items():
                rows.append({
                    "חברה":      t,
                    "Fwd P/E":   fmt_num(safe_get(pinfo, "forwardPE")),
                    "EV/EBITDA": fmt_num(safe_get(pinfo, "enterpriseToEbitda")),
                    "P/S":       fmt_num(safe_get(pinfo, "priceToSalesTrailing12Months")),
                    "P/B":       fmt_num(safe_get(pinfo, "priceToBook")),
                    "ROE":       fmt_pct(safe_get(pinfo, "returnOnEquity")),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        with col_chart:
            fig = chart_peer_forward_pe(ticker, info, peer_data)
            if fig.data:
                st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"שגיאה בסעיף הערכת שווי: {e}")

    st.markdown("---")

    # Bottom 4 cards
    cc1, cc2, cc3, cc4 = st.columns(4)

    with cc1:
        try:
            rtl_header("מאזן")
            de = safe_get(info, "debtToEquity")
            de_str = fmt_num(float(de) / 100) if de else "N/A"
            st.markdown(
                f'<div class="card">'
                f'<div dir="rtl" style="margin-bottom:6px;"><span style="color:{COLOR_MUTED}">FCF: </span>{fmt_currency(safe_get(info,"freeCashflow"),"B")}</div>'
                f'<div dir="rtl" style="margin-bottom:6px;"><span style="color:{COLOR_MUTED}">מזומן: </span>{fmt_currency(safe_get(info,"totalCash"),"B")}</div>'
                f'<div dir="rtl" style="margin-bottom:6px;"><span style="color:{COLOR_MUTED}">Debt/Equity: </span>{de_str}</div>'
                f'<div dir="rtl"><span style="color:{COLOR_MUTED}">Current Ratio: </span>{fmt_num(safe_get(info,"currentRatio"))}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            pass

    with cc2:
        try:
            rtl_header("ROIC vs. WACC")
            fin_ok   = fin is not None and len(fin) > 0
            bs_ok    = bs  is not None and len(bs)  > 0
            roic     = calc_roic(fin, bs) if (fin_ok and bs_ok) else float("nan")
            wacc_pct = wacc * 100
            spread   = (roic - wacc_pct) if not np.isnan(roic) else float("nan")
            sp_clr   = COLOR_GREEN if (not np.isnan(spread) and spread > 0) else COLOR_RED
            sp_str   = f"{spread:+.1f}%" if not np.isnan(spread) else "N/A"
            st.markdown(
                f'<div class="card">'
                f'<div dir="rtl" style="margin-bottom:6px;">ROIC: <span style="color:{COLOR_GREEN}; font-weight:600;">{fmt_num(roic)}%</span></div>'
                f'<div dir="rtl" style="margin-bottom:6px;">WACC (est.): <span style="color:{COLOR_YELLOW}; font-weight:600;">{wacc_pct:.1f}%</span></div>'
                f'<div dir="rtl">Spread: <span style="color:{sp_clr}; font-weight:600;">{sp_str}</span></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            pass

    with cc3:
        try:
            rtl_header("הקצאת הון")
            buybacks = divs_paid = rnd_spend = None
            if cf is not None and len(cf) > 0:
                for key in ["Repurchase Of Capital Stock", "Common Stock Repurchased"]:
                    if key in cf.index:
                        buybacks = abs(float(cf.loc[key].iloc[0]))
                        break
                for key in ["Cash Dividends Paid", "Common Stock Dividend Paid"]:
                    if key in cf.index:
                        divs_paid = abs(float(cf.loc[key].iloc[0]))
                        break
            if fin is not None and len(fin) > 0:
                for key in ["Research And Development"]:
                    if key in fin.index:
                        rnd_spend = float(fin.loc[key].iloc[0])
                        break
            st.markdown(
                f'<div class="card">'
                f'<div dir="rtl" style="margin-bottom:6px;"><span style="color:{COLOR_MUTED}">Buybacks: </span>{fmt_currency(buybacks,"B")}</div>'
                f'<div dir="rtl" style="margin-bottom:6px;"><span style="color:{COLOR_MUTED}">Dividends: </span>{fmt_currency(divs_paid,"B")}</div>'
                f'<div dir="rtl"><span style="color:{COLOR_MUTED}">R&D: </span>{fmt_currency(rnd_spend,"B")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            pass

    with cc4:
        try:
            rtl_header("ציון איכות")
            scores = calc_quality_scores(info, fin, bs)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            for label, score in scores.items():
                st.markdown(
                    f'<div dir="rtl" style="font-size:0.8rem; margin-bottom:2px;">'
                    f'{label}: <span style="color:{COLOR_GREEN}">{score:.1f}/10</span></div>',
                    unsafe_allow_html=True,
                )
                st.progress(score / 10)
            st.markdown('</div>', unsafe_allow_html=True)
        except Exception:
            pass

    st.session_state["peer_data_cache"] = peer_data


# ── Page 2: Technical + Sentiment ─────────────────────────────────────────────
def render_technical(ticker: str, data: dict) -> None:
    info = data.get("info", {})
    hist = data.get("history", pd.DataFrame())
    inst = data.get("institutional_holders", pd.DataFrame())
    recs = data.get("recommendations", pd.DataFrame())
    apt  = data.get("analyst_price_targets", {})

    sector   = safe_get(info, "sector",   "Default") or "Default"
    industry = safe_get(info, "industry", "")        or ""
    peers    = get_peers(sector, industry)

    long_name = safe_get(info, "longName", ticker) or ticker
    st.markdown(
        f'<h2 style="color:{COLOR_WHITE}; direction:rtl; text-align:right; margin-bottom:8px;">'
        f'{long_name} | טכני + אנליסטים + סטאפ</h2>',
        unsafe_allow_html=True,
    )

    close    = hist["Close"] if hist is not None and len(hist) > 0 else pd.Series(dtype=float)
    rsi_val  = calc_rsi(close)  if len(close) > 14 else float("nan")
    macd_data = calc_macd(close) if len(close) > 26 else {"label": "N/A"}

    # KPI row
    try:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1: st.metric("Beta",          fmt_num(safe_get(info, "beta")))
        with c2: st.metric("RSI 14D",       fmt_num(rsi_val))
        with c3: st.metric("MACD",          macd_data.get("label", "N/A"))
        with c4:
            ma50 = safe_get(info, "fiftyDayAverage")
            st.metric("50DMA", f"${float(ma50):.2f}" if ma50 else "N/A")
        with c5:
            ma200 = safe_get(info, "twoHundredDayAverage")
            st.metric("200DMA", f"${float(ma200):.2f}" if ma200 else "N/A")
        with c6:
            apt_mean = apt.get("mean") if isinstance(apt, dict) else None
            st.metric("Analyst Target", f"${float(apt_mean):.2f}" if apt_mean else "N/A")
    except Exception as e:
        st.warning(f"שגיאה ב-KPIs טכניים: {e}")

    st.markdown("---")

    # Section 4: ביצועי YTD
    rtl_header("4. ביצועי YTD vs. עמיתים")
    try:
        all_ytd = tuple([ticker] + peers + ["^IXIC", "^GSPC"])
        with st.spinner("טוען ביצועי YTD..."):
            ytd_histories = fetch_ytd_history(all_ytd)
        fig = chart_ytd_performance(ticker, peers, ytd_histories)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("אין נתוני YTD זמינים")
    except Exception as e:
        st.warning(f"שגיאה בסעיף YTD: {e}")

    # Section 5: אנליסטים
    rtl_header("5. אנליסטים")
    try:
        col_pie, col_table = st.columns([1, 1])
        with col_pie:
            if recs is not None and len(recs) > 0:
                fig = chart_analyst_ratings(recs)
                if fig.data:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("אין נתוני המלצות")
            else:
                st.info("אין נתוני המלצות אנליסטים")
        with col_table:
            if recs is not None and len(recs) > 0:
                valid_cols = [c for c in ["period", "strongBuy", "buy", "hold", "sell", "strongSell"]
                              if c in recs.columns]
                if valid_cols:
                    rename_map = {"period": "תקופה", "strongBuy": "Strong Buy", "buy": "Buy",
                                  "hold": "Hold", "sell": "Sell", "strongSell": "Strong Sell"}
                    st.dataframe(
                        recs[valid_cols].head(5).rename(columns=rename_map),
                        use_container_width=True, hide_index=True,
                    )
            if isinstance(apt, dict) and apt:
                apt_mean = apt.get("mean")
                apt_high = apt.get("high")
                apt_low  = apt.get("low")
                if apt_mean:
                    help_txt = (f"High: ${float(apt_high):.2f}  |  Low: ${float(apt_low):.2f}"
                                if apt_high and apt_low else None)
                    st.metric("Consensus Target", f"${float(apt_mean):.2f}", help=help_txt)
    except Exception as e:
        st.warning(f"שגיאה בסעיף אנליסטים: {e}")

    # Section 6: סטאפ טכני
    rtl_header("6. סטאפ טכני")
    try:
        price    = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice") or 0
        high_52w = safe_get(info, "fiftyTwoWeekHigh")  or 0
        low_52w  = safe_get(info, "fiftyTwoWeekLow")   or 0
        ma50     = safe_get(info, "fiftyDayAverage")   or 0
        ma200    = safe_get(info, "twoHundredDayAverage") or 0

        fib = calc_fibonacci_levels(float(high_52w), float(low_52w))
        level_rows = []
        for name, level in fib.items():
            if level:
                above = float(price) >= float(level)
                level_rows.append({"רמה": name, "מחיר": f"${float(level):.2f}",
                                    "סטטוס": "מעל ✓" if above else "מתחת ✗"})
        if ma50:
            level_rows.append({"רמה": "50 MA",  "מחיר": f"${float(ma50):.2f}",
                                "סטטוס": "מעל ✓" if float(price) > float(ma50) else "מתחת ✗"})
        if ma200:
            level_rows.append({"רמה": "200 MA", "מחיר": f"${float(ma200):.2f}",
                                "סטטוס": "מעל ✓" if float(price) > float(ma200) else "מתחת ✗"})

        if level_rows:
            df_levels = pd.DataFrame(level_rows)
            def _style_status(val):
                if "מעל" in str(val):
                    return f"color: {COLOR_GREEN}; font-weight: bold"
                return f"color: {COLOR_RED}; font-weight: bold"
            st.dataframe(df_levels.style.map(_style_status, subset=["סטטוס"]),
                         use_container_width=True, hide_index=True)

        above_50  = float(price) > float(ma50)  if ma50  else False
        above_200 = float(price) > float(ma200) if ma200 else False
        if above_50 and above_200:
            setup_text, setup_color = "שורי 🐂", COLOR_GREEN
        elif above_50 or above_200:
            setup_text, setup_color = "מעורב ↔", COLOR_YELLOW
        else:
            setup_text, setup_color = "דובי 🐻", COLOR_RED

        rsi_str   = f"RSI {fmt_num(rsi_val)}" if not np.isnan(rsi_val) else "RSI N/A"
        macd_lbl  = macd_data.get("label", "N/A")
        macd_clr  = COLOR_GREEN if macd_lbl == "BULLISH" else COLOR_RED
        st.markdown(
            f'<div class="card" dir="rtl">'
            f'<span style="color:{COLOR_MUTED}">סטאפ כולי: </span>'
            f'<span style="color:{setup_color}; font-weight:700">{setup_text}</span>'
            f' &nbsp;|&nbsp; {rsi_str}'
            f' &nbsp;|&nbsp; MACD: <span style="color:{macd_clr}">{macd_lbl}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.warning(f"שגיאה בסעיף טכני: {e}")

    # Section 7: מוסדיים
    rtl_header("7. מחזיקים מוסדיים")
    try:
        if inst is not None and len(inst) > 0:
            top5 = inst.head(5).copy()
            col_rename = {}
            if "Holder" in top5.columns:    col_rename["Holder"] = "מחזיק"
            if "Value"  in top5.columns:    col_rename["Value"]  = "שווי ($)"
            if "% Out"  in top5.columns:    col_rename["% Out"]  = "% החזקה"
            if "pctChange" in top5.columns:
                top5["שינוי"] = top5["pctChange"].apply(
                    lambda x: f"+{x*100:.1f}%" if (x and x > 0) else (f"{x*100:.1f}%" if x else "N/A")
                )
            top5 = top5.rename(columns=col_rename)
            display_cols = [c for c in ["מחזיק", "שווי ($)", "% החזקה", "שינוי"] if c in top5.columns]
            st.dataframe(top5[display_cols] if display_cols else top5,
                         use_container_width=True, hide_index=True)
        else:
            st.info("אין נתוני מחזיקים מוסדיים")
    except Exception as e:
        st.warning(f"שגיאה בסעיף מוסדיים: {e}")

    # Section 8: קטליזטורים וסיכונים
    rtl_header("8. קטליזטורים וסיכונים")
    try:
        summary  = safe_get(info, "longBusinessSummary", "") or ""
        catalysts, risks = extract_catalysts_risks(summary, sector)
        col_cat, col_risk = st.columns(2)
        with col_cat:
            bullets_html = "".join(
                f'<div style="color:{COLOR_GREEN}; margin-bottom:6px; font-size:0.85rem;">• {c}</div>'
                for c in catalysts
            )
            st.markdown(
                f'<div class="card" dir="rtl">'
                f'<div style="color:{COLOR_GREEN}; font-weight:700; margin-bottom:8px;">✦ קטליזטורים חיוביים</div>'
                f'{bullets_html}</div>',
                unsafe_allow_html=True,
            )
        with col_risk:
            bullets_html = "".join(
                f'<div style="color:{COLOR_RED}; margin-bottom:6px; font-size:0.85rem;">• {r}</div>'
                for r in risks
            )
            st.markdown(
                f'<div class="card" dir="rtl">'
                f'<div style="color:{COLOR_RED}; font-weight:700; margin-bottom:8px;">⚠ סיכונים עיקריים</div>'
                f'{bullets_html}</div>',
                unsafe_allow_html=True,
            )
    except Exception as e:
        st.warning(f"שגיאה בסעיף קטליזטורים: {e}")

    # Section 9: תרחישים 3 שנים
    rtl_header("9. תרחישים — 3 שנים קדימה")
    try:
        price = float(safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice") or 100)
        eg    = float(safe_get(info, "earningsGrowth") or 0.10)
        if eg < -0.5:
            eg = 0.05
        bull_growth = max(eg, 0.15)
        base_growth = max(eg * 0.7, 0.03)
        bull_t = price * ((1 + bull_growth) ** 3) * 1.10
        base_t = price * ((1 + base_growth) ** 3) * 1.00
        bear_t = price * ((1 - 0.05)        ** 3) * 0.80
        cc1, cc2, cc3 = st.columns(3)
        for col, label, target, clr, css_class, prob, growth_label in [
            (cc1, "BULL 🐂", bull_t, COLOR_GREEN,  "scenario-bull", "25%", f"{bull_growth*100:.0f}%/y | PE ×1.10"),
            (cc2, "BASE 📊", base_t, COLOR_YELLOW, "scenario-base", "50%", f"{base_growth*100:.0f}%/y | PE ×1.00"),
            (cc3, "BEAR 🐻", bear_t, COLOR_RED,    "scenario-bear", "25%", "-5%/y | PE ×0.80"),
        ]:
            ret = (target / price - 1) * 100
            with col:
                st.markdown(
                    f'<div class="{css_class}">'
                    f'<div style="color:{clr}; font-size:1.05rem; font-weight:700;">{label}</div>'
                    f'<div style="color:{COLOR_MUTED}; font-size:0.78rem; margin-top:4px;">הסתברות: {prob}</div>'
                    f'<div style="font-size:1.6rem; font-weight:700; color:{clr}; margin:10px 0;">${target:.2f}</div>'
                    f'<div style="color:{clr}; font-size:0.85rem;">{ret:+.1f}% vs. נוכחי</div>'
                    f'<div style="color:{COLOR_MUTED}; font-size:0.72rem; margin-top:6px;">{growth_label}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    except Exception as e:
        st.warning(f"שגיאה בסעיף תרחישים: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    st.set_page_config(
        page_title="Stock Analyzer | מנתח מניות",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    # ── API key guard ─────────────────────────────────────────────────────────
    if not os.environ.get("FMP_API_KEY"):
        st.error(
            "❌ **Missing FMP_API_KEY** — add it as an environment variable in Render.\n\n"
            "Get a free key at https://financialmodelingprep.com/developer/docs"
        )
        st.stop()

    ticker, analyze_clicked = render_sidebar()

    if analyze_clicked and ticker:
        st.session_state["last_ticker"]  = ticker
        st.session_state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        st.session_state.pop("export_data",     None)
        st.session_state.pop("peer_data_cache", None)

    active_ticker = st.session_state.get("last_ticker", "")

    if not active_ticker:
        st.markdown(
            f'<div style="text-align:center; margin-top:100px; color:{COLOR_MUTED};">'
            f'<div style="font-size:4rem;">📊</div>'
            f'<div style="font-size:1.2rem; margin-top:16px; direction:rtl;">'
            f'הזן סימול מניה בסרגל הצד ולחץ Analyze</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    debug_fmp_connection()   # ← DEBUG: remove once API is confirmed working

    with st.spinner(f"טוען נתונים עבור {active_ticker}..."):
        data = fetch_ticker_data(active_ticker)

    info = data.get("info", {})
    if not info or not info.get("symbol"):
        st.error(
            f"❌ לא נמצאו נתונים עבור '{active_ticker}'. "
            f"בדוק שהסימול נכון (לדוגמה: AAPL, NVDA, MSFT)."
        )
        return

    # Build export (peer fetch already cached)
    if "export_data" not in st.session_state:
        try:
            peers     = get_peers(safe_get(info, "sector", "Default") or "Default",
                                  safe_get(info, "industry", "") or "")
            peer_data = fetch_peer_data(tuple(peers))
            st.session_state["export_data"] = build_excel_export(active_ticker, data, peer_data)
        except Exception:
            pass

    tab1, tab2 = st.tabs(["📊 פונדמנטלס", "📈 טכני + סנטימנט"])
    with tab1:
        render_fundamentals(active_ticker, data)
    with tab2:
        render_technical(active_ticker, data)


if __name__ == "__main__":
    main()
