# ============================================================================
#  SURGE  ·  live momentum stock scanner
#  Stocks up 5–10% today, on heavy volume, with a fresh news catalyst.
#
#  Data:   yfinance (price, volume, float, analyst targets)  — no key needed
#          Finnhub  (company news)                            — free API key
#  Charts: TradingView widget (live 1-min price) + per-minute volume
#
#  You do NOT need to understand this code to run it. Follow DEPLOY_GUIDE.md.
#  To change how it behaves, tell Claude what you want and paste back the new file.
# ============================================================================

import datetime as dt
import altair as alt
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf

try:
    import finnhub
except Exception:
    finnhub = None

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# ----------------------------------------------------------------------------
# PAGE SETUP
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Surge Scanner", page_icon="📈", layout="wide",
                   initial_sidebar_state="expanded")

# ---- Surge look & feel (dark, amber beacon accent) -------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

:root { --accent:#f0a63a; --accent-soft:#3a2c14; --ink:#e9edf5; --ink2:#a6b0c3; --ink3:#6b7690;
        --surface:#141924; --surface2:#1a202d; --line:#262e3d; --line2:#37415a;
        --up:#2ecb8f; --down:#f0685a; }
.stApp { background:#0b0e15; }
#MainMenu, footer {visibility:hidden;}   /* keep header so the sidebar arrow stays visible */
.block-container{ padding-top:1.4rem; padding-bottom:3rem; max-width:1180px; }
html, body, [class*="css"]{ font-family:"IBM Plex Sans",system-ui,-apple-system,sans-serif; }
h1,h2,h3,h4,p,span,div,label,li { color:var(--ink); }
h1,h2,h3 { font-family:"Archivo",sans-serif; letter-spacing:-.4px; }
.mono, .mono * { font-family:"IBM Plex Mono",monospace; }
hr { border-color:var(--line) !important; }

/* brand */
.beacon-row{display:flex;align-items:center;gap:12px;}
.beacon{width:36px;height:36px;border-radius:11px;background:radial-gradient(circle at 50% 36%,#f0a63a,#a9680f);
        display:grid;place-items:center;box-shadow:0 0 0 4px var(--accent-soft);flex:none;}
.beacon::after{content:"";width:9px;height:9px;border-radius:50%;background:#fff;}
.wordmark{font-family:"Archivo",sans-serif;font-weight:800;font-size:25px;letter-spacing:-.6px;line-height:1;}
.wordmark span{color:var(--accent);}
.tagline{font-size:12px;color:var(--ink3);letter-spacing:.2px;margin-top:2px;}

/* consistent section header */
.sec-wrap{margin:8px 0 16px;}
.sec-eyebrow{font-size:11px;font-weight:700;letter-spacing:1.6px;text-transform:uppercase;color:var(--accent);}
.sec-title{font-family:"Archivo",sans-serif;font-weight:800;font-size:23px;letter-spacing:-.4px;margin:3px 0 4px;}
.sec-desc{font-size:13px;color:var(--ink3);line-height:1.55;max-width:74ch;}

/* the 3-signal chips */
.chips{display:flex;gap:9px;flex-wrap:wrap;margin:2px 0 14px;}
.chip{display:inline-flex;align-items:center;gap:8px;padding:7px 13px;border-radius:999px;font-size:12.5px;
      font-weight:600;background:var(--surface);border:1px solid var(--line);color:var(--ink);}
.chip .k{width:19px;height:19px;border-radius:50%;display:grid;place-items:center;font-size:11px;color:#0b0e15;font-weight:700;}
.chip .v{color:var(--ink3);font-family:"IBM Plex Mono",monospace;font-weight:500;}

/* radios → clean segmented pills (used for the section switch & filters) */
div[role="radiogroup"]{ flex-direction:row; flex-wrap:wrap; gap:8px; }
div[role="radiogroup"] > label{
    background:var(--surface); border:1px solid var(--line); border-radius:999px;
    padding:7px 15px; margin:0; cursor:pointer; transition:.15s; }
div[role="radiogroup"] > label:hover{ border-color:var(--line2); }
div[role="radiogroup"] > label:has(input:checked){
    background:var(--accent-soft); border-color:var(--accent); }
div[role="radiogroup"] > label:has(input:checked) p{ color:#f4bd63; font-weight:600; }
div[role="radiogroup"] > label > div:first-child{ display:none; }   /* hide the radio dot */

/* tabs (session tabs) */
[data-baseweb="tab-list"]{ gap:4px; border-bottom:1px solid var(--line); }
button[data-baseweb="tab"]{ font-weight:600; color:var(--ink3); }
button[data-baseweb="tab"][aria-selected="true"]{ color:#f4bd63; }
[data-baseweb="tab-highlight"]{ background:var(--accent) !important; }

/* metrics → tidy cards */
[data-testid="stMetric"]{ background:var(--surface); border:1px solid var(--line);
    border-radius:13px; padding:12px 15px; }
[data-testid="stMetricLabel"]{ color:var(--ink3); }
[data-testid="stMetricValue"]{ font-family:"IBM Plex Mono",monospace; font-weight:600; }

/* buttons */
div.stButton > button{ border-radius:9px; border:1px solid var(--line); background:var(--surface);
    color:var(--ink); font-weight:600; transition:.15s; }
div.stButton > button:hover{ border-color:var(--accent); color:#f4bd63; }

/* dataframe frame */
[data-testid="stDataFrame"]{ border:1px solid var(--line); border-radius:12px; }

.tag{font-size:9.5px;font-weight:700;letter-spacing:.4px;padding:2px 6px;border-radius:5px;}
.tag.low{color:#f4bd63;background:var(--accent-soft);} .tag.mid{color:var(--ink2);background:#212836;}

/* ---- left sidebar as a nav rail (hypurrintel-style) ---- */
[data-testid="stSidebar"]{ background:#0e121b; border-right:1px solid var(--line); }
[data-testid="stSidebar"] .block-container{ padding-top:1.4rem; }
[data-testid="stSidebar"] div[role="radiogroup"]{ flex-direction:column; gap:5px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label{
    width:100%; border-radius:10px; border:1px solid transparent; background:transparent;
    padding:11px 13px; font-size:14px; font-weight:600; color:var(--ink2); transition:.14s; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:hover{ background:var(--surface); border-color:var(--line); }
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked){
    background:var(--accent-soft); border-color:var(--accent); box-shadow:inset 3px 0 0 var(--accent); }
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p{ color:#f4bd63; }
.navlabel{ font-size:10.5px; font-weight:700; letter-spacing:1.5px; text-transform:uppercase;
    color:var(--ink3); margin:14px 2px 8px; }

/* ---- on-page filter panel ---- */
.filterhead{ font-size:11px; font-weight:700; letter-spacing:1.3px; text-transform:uppercase;
    color:var(--ink3); margin:0 0 -4px; }
[data-testid="stExpander"]{ border:1px solid var(--line) !important; border-radius:13px !important;
    background:var(--surface); }
[data-testid="stSlider"] label, [data-testid="stCheckbox"] label, [data-testid="stSelectbox"] label{
    font-size:12px; color:var(--ink2); font-weight:600; }
</style>
""", unsafe_allow_html=True)


def section_header(eyebrow, title, desc):
    st.markdown(
        f"<div class='sec-wrap'><div class='sec-eyebrow'>{eyebrow}</div>"
        f"<div class='sec-title'>{title}</div><div class='sec-desc'>{desc}</div></div>",
        unsafe_allow_html=True)

# (Section nav lives in the left sidebar; stock filters live on the page — both built below.)

# auto-refresh every 120s
if st_autorefresh:
    st_autorefresh(interval=120 * 1000, key="surge_refresh")

try:
    FINNHUB_KEY = st.secrets.get("FINNHUB_KEY", "")
except Exception:
    FINNHUB_KEY = ""   # no secrets file yet — app still runs, just without news

# ----------------------------------------------------------------------------
# S&P 500 membership — fetched live from Wikipedia (cached 1 day), with a
# small built-in fallback so classification still works if the fetch fails.
# ----------------------------------------------------------------------------
SP500_FALLBACK = {
    "AAPL","MSFT","NVDA","AMZN","GOOGL","GOOG","META","BRK-B","LLY","AVGO","TSLA",
    "JPM","V","XOM","UNH","MA","JNJ","PG","HD","COST","ABBV","MRK","CVX","WMT",
    "KO","PEP","BAC","CRM","ADBE","NFLX","AMD","TMO","MCD","CSCO","ACN","LIN",
    "ABT","DHR","INTC","QCOM","TXN","VZ","DIS","WFC","PM","INTU","CAT","IBM",
    "GE","NOW","AMGN","UBER","BA","GS","HON","SPGI","LOW","BKNG","PFE","ELV",
    "T","SCHW","BLK","C","AXP","DE","ISRG","NKE","MDT","PLD","LMT","SYK","TJX",
    "MS","BMY","ADP","GILD","MMC","REGN","VRTX","CB","ETN","SBUX","MU","PANW",
    "KLAC","LRCX","SNPS","CDNS","ORLY","MAR","MNST","FTNT","ADSK","PYPL","CRWD",
}

@st.cache_data(ttl=86400, show_spinner=False)
def get_sp500_map():
    """{ticker: GICS sector} for the S&P 500, from Wikipedia (cached daily)."""
    try:
        t = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        m = {}
        for _, row in t.iterrows():
            sym = str(row["Symbol"]).replace(".", "-")
            m[sym] = str(row.get("GICS Sector", "—"))
        if len(m) > 400:
            return m
    except Exception:
        pass
    return {s: "—" for s in SP500_FALLBACK}

@st.cache_data(ttl=86400, show_spinner=False)
def get_sp500():
    return set(get_sp500_map().keys())

# ----------------------------------------------------------------------------
# DATA LAYER  (cached so we stay well inside free rate limits)
# ----------------------------------------------------------------------------
@st.cache_data(ttl=120, show_spinner=False)
def get_universe():
    """Union of Yahoo's ready-made mover lists — no scanning 8,000 tickers."""
    syms = []
    for screen in ("day_gainers", "most_actives", "small_cap_gainers"):
        try:
            res = yf.screen(screen, count=60)
            for q in res.get("quotes", []):
                s = q.get("symbol")
                if s and s.isalpha():        # skip odd tickers/warrants
                    syms.append(s)
        except Exception:
            continue
    # de-dupe, keep order
    seen, out = set(), []
    for s in syms:
        if s not in seen:
            seen.add(s); out.append(s)
    return out[:70]

@st.cache_data(ttl=120, show_spinner=False)
def get_stock(sym):
    """Fetch the fields we need for one ticker. Returns None on failure."""
    try:
        info = yf.Ticker(sym).info or {}
    except Exception:
        return None
    price = info.get("regularMarketPrice") or info.get("currentPrice")
    prev  = info.get("regularMarketPreviousClose") or info.get("previousClose")
    vol   = info.get("regularMarketVolume") or info.get("volume")
    avol  = info.get("averageVolume") or info.get("averageVolume10days")
    if not all([price, prev, vol, avol]) or prev == 0 or avol == 0:
        return None
    return {
        "sym": sym,
        "name": info.get("shortName") or info.get("longName") or sym,
        "sector": info.get("sector") or info.get("industry") or "—",
        "price": float(price),
        "prev": float(prev),
        "chg": (float(price) - float(prev)) / float(prev) * 100,
        "vol": int(vol),
        "avol": int(avol),
        "rvol": float(vol) / float(avol),
        "float": info.get("floatShares"),
        "target": info.get("targetMeanPrice"),
        "target_hi": info.get("targetHighPrice"),
        "target_lo": info.get("targetLowPrice"),
        "n_analysts": info.get("numberOfAnalystOpinions"),
        "pre_price": info.get("preMarketPrice"),
        "post_price": info.get("postMarketPrice"),
    }

@st.cache_data(ttl=180, show_spinner=False)
def get_news(sym, within_hours):
    """Latest company news from Finnhub: the lead story + more recent coverage."""
    if not (finnhub and FINNHUB_KEY):
        return None
    try:
        client = finnhub.Client(api_key=FINNHUB_KEY)
        today = dt.date.today()
        items = client.company_news(
            sym, _from=str(today - dt.timedelta(days=3)), to=str(today))
        if not items:
            return None
        items.sort(key=lambda x: x.get("datetime", 0), reverse=True)

        def mins_of(it):
            return int((dt.datetime.now()
                        - dt.datetime.fromtimestamp(it.get("datetime", 0))).total_seconds() / 60)

        top = items[0]
        if mins_of(top) > within_hours * 60:
            return None
        # up to 4 more recent headlines for the "more coverage" list
        more = [{"headline": it.get("headline", ""), "source": it.get("source", ""),
                 "url": it.get("url", ""), "mins": mins_of(it)}
                for it in items[1:5] if it.get("headline")]
        return {"headline": top.get("headline", ""),
                "source": top.get("source", ""),
                "url": top.get("url", ""),
                "summary": top.get("summary", ""),
                "mins": mins_of(top),
                "count": len(items),
                "more": more}
    except Exception:
        return None

@st.cache_data(ttl=120, show_spinner=False)
def get_minutes(sym):
    """1-minute bars incl. pre/post market for the volume charts."""
    try:
        h = yf.Ticker(sym).history(period="1d", interval="1m", prepost=True)
        if h.empty:
            return None
        h = h.tz_convert("America/New_York")
        return h
    except Exception:
        return None

@st.cache_data(ttl=600, show_spinner=False)
def get_sp_spikes(rvol_min):
    """Scan ALL S&P 500 names in one batched download; return those whose volume
    is running well above their 20-day average (a 'spike') — no other filters."""
    smap = get_sp500_map()
    tickers = sorted(smap.keys())
    try:
        data = yf.download(tickers, period="1mo", interval="1d", group_by="ticker",
                           threads=True, progress=False, auto_adjust=False)
    except Exception:
        return None
    if data is None or len(data) == 0:
        return None
    level0 = set(data.columns.get_level_values(0)) if hasattr(data.columns, "get_level_values") else set()
    valid, rows = 0, []
    for t in tickers:
        try:
            if t not in level0:
                continue
            d = data[t]
            vol = d["Volume"].dropna()
            close = d["Close"].dropna()
            if len(vol) < 6 or len(close) < 2:
                continue
            avg_v = float(vol.iloc[:-1].tail(20).mean())
            today_v = float(vol.iloc[-1])
            if avg_v <= 0 or today_v <= 0:
                continue
            valid += 1
            rvol = today_v / avg_v
            if rvol < rvol_min:
                continue
            price = float(close.iloc[-1]); prev = float(close.iloc[-2])
            rows.append({
                "sym": t, "sector": smap.get(t, "—"),
                "price": price, "chg": (price - prev) / prev * 100 if prev else 0.0,
                "rvol": rvol, "vol": today_v,
                "excess": max(0.0, (today_v - avg_v)) * price,   # $ of *extra* volume
            })
        except Exception:
            continue
    if valid == 0:
        return None
    return pd.DataFrame(rows)

# ----------------------------------------------------------------------------
# RUN THE SCAN
# ----------------------------------------------------------------------------
def fmt_vol(v):
    if v is None: return "—"
    if v >= 1e6: return f"{v/1e6:.1f}M"
    if v >= 1e3: return f"{v/1e3:.0f}K"
    return f"{int(v)}"

def fmt_float(f):
    if not f: return "—"
    return f"{f/1e6:.1f}M"

def ago(m):
    return f"{m}m ago" if m < 60 else f"{m//60}h {m%60}m ago"

# ---- market pulse: index context at the top, like the pro scanners ----
@st.cache_data(ttl=120, show_spinner=False)
def get_market_pulse():
    out = {}
    try:
        d = yf.download(["SPY", "QQQ", "^VIX"], period="5d", interval="1d",
                        progress=False, auto_adjust=False, group_by="ticker")
        for sym, key in [("SPY", "spy"), ("QQQ", "qqq"), ("^VIX", "vix")]:
            try:
                c = d[sym]["Close"].dropna()
                last, prev = float(c.iloc[-1]), float(c.iloc[-2])
                out[key] = {"last": last, "chg": (last - prev) / prev * 100}
            except Exception:
                pass
    except Exception:
        return {}
    return out

def market_pulse_strip():
    try:
        p = get_market_pulse()
        if not p:
            return
        cols = st.columns(3)
        if p.get("spy"):
            cols[0].metric("S&P 500 (SPY)", f"${p['spy']['last']:.2f}", f"{p['spy']['chg']:+.2f}%")
        if p.get("qqq"):
            cols[1].metric("Nasdaq (QQQ)", f"${p['qqq']['last']:.2f}", f"{p['qqq']['chg']:+.2f}%")
        if p.get("vix"):
            cols[2].metric("Volatility (VIX)", f"{p['vix']['last']:.1f}", f"{p['vix']['chg']:+.1f}%",
                           delta_color="inverse")
    except Exception:
        pass

# ---- color-code a board so it reads at a glance (best-effort; degrades cleanly) ----
def style_board(df):
    def chg_color(v):
        try:
            return "color:#2ecb8f" if float(v) >= 0 else "color:#f0685a"
        except Exception:
            return ""
    def rvol_color(v):
        try:
            v = float(v)
            return "color:#f0685a;font-weight:600" if v >= 4 else ("color:#f4bd63" if v >= 2.5 else "")
        except Exception:
            return ""
    sty = df.style
    for c in df.columns:
        if c in ("% Chg", "Target"):
            sty = sty.map(chg_color, subset=[c])
        elif c == "R.Vol":
            sty = sty.map(rvol_color, subset=[c])
    return sty

import zoneinfo

def et_now():
    return dt.datetime.now(zoneinfo.ZoneInfo("America/New_York"))

def current_session():
    """Which US market session is live right now (ET)."""
    t = et_now().time()
    if dt.time(4, 0) <= t < dt.time(9, 30):  return "pre"
    if dt.time(9, 30) <= t < dt.time(16, 0): return "live"
    if dt.time(16, 0) <= t < dt.time(20, 0): return "post"
    return "closed"

def load_universe():
    """One pass over the mover lists → every candidate with its regular-session numbers."""
    sp = get_sp500()
    out = []
    for sym in get_universe():
        d = get_stock(sym)
        if not d:
            continue
        d["sp500"] = sym in sp
        out.append(d)
    return out

def session_volume(h, sess):
    """Sum 1-minute volume within a session window (pre / regular / post)."""
    if h is None or h.empty:
        return None
    times = h.index.time
    if sess == "pre":
        mask = [t < dt.time(9, 30) for t in times]
    elif sess == "post":
        mask = [t >= dt.time(16, 0) for t in times]
    else:
        mask = [dt.time(9, 30) <= t < dt.time(16, 0) for t in times]
    return int(h["Volume"][mask].sum())

def apply_market_filter(stocks, view):
    if view.startswith("S&P"):
        return [d for d in stocks if d.get("sp500")]
    if view.startswith("Outside"):
        return [d for d in stocks if not d.get("sp500")]
    return stocks

def scan_regular(stocks):
    """The core live-session scan: up 5–10%, heavy volume, fresh news."""
    rows = []
    for d in stocks:
        if not (chg_min <= d["chg"] <= chg_max): continue
        if d["rvol"] < rvol_min: continue
        if not (price_min <= d["price"] <= price_max): continue
        d["news"] = get_news(d["sym"], news_hours)
        if require_news and not d["news"]:
            continue
        rows.append(d)
    rows.sort(key=lambda x: x["vol"], reverse=True)
    return rows[:top_n]

def scan_session(stocks, sess):
    """Pre-market or after-hours movers, with true session volume from minute bars."""
    price_key = "pre_price" if sess == "pre" else "post_price"
    cand = []
    for d in stocks:
        sp_price = d.get(price_key)
        base = d["prev"] if sess == "pre" else d["price"]  # pre vs prior close; post vs regular close
        if not sp_price or not base:
            continue
        chg = (float(sp_price) - base) / base * 100
        if not (chg_min <= chg <= chg_max): continue
        if not (price_min <= float(sp_price) <= price_max): continue
        e = dict(d); e["s_price"] = float(sp_price); e["s_chg"] = chg
        cand.append(e)
    # bound the minute-bar fetches: rank by regular volume, keep top_n, then get true session volume
    cand.sort(key=lambda x: x["vol"], reverse=True)
    cand = cand[:top_n]
    for e in cand:
        e["s_vol"] = session_volume(get_minutes(e["sym"]), sess)
        e["news"] = get_news(e["sym"], news_hours)
    if require_news:
        cand = [c for c in cand if c.get("news")]
    cand.sort(key=lambda x: (x.get("s_vol") or 0), reverse=True)
    return cand

# ============================================================================
#  WHALE TRACKER (Hyperliquid) — crypto is transparent, so wallets are public
# ============================================================================
HL_INFO = "https://api.hyperliquid.xyz/info"
HL_LEADERBOARD = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"

def get_follows():
    raw = st.query_params.get("follow", "")
    return [a for a in raw.split(",") if a]

def set_follows(lst):
    if lst:
        st.query_params["follow"] = ",".join(lst)
    else:
        try:
            del st.query_params["follow"]
        except Exception:
            st.query_params["follow"] = ""

@st.cache_data(ttl=300, show_spinner=False)
def hl_leaderboard():
    """Top Hyperliquid traders from the public stats endpoint (may change/lag)."""
    try:
        rows = requests.get(HL_LEADERBOARD, timeout=12).json().get("leaderboardRows", [])
        out = []
        for r in rows:
            perf = {w[0]: w[1] for w in r.get("windowPerformances", [])}
            allt = perf.get("allTime", {}) or {}
            day = perf.get("day", {}) or {}
            out.append({
                "address": r.get("ethAddress", ""),
                "accountValue": float(r.get("accountValue", 0) or 0),
                "pnlAll": float(allt.get("pnl", 0) or 0),
                "roiAll": float(allt.get("roi", 0) or 0),
                "vlm": float(day.get("vlm", 0) or 0),
            })
        return out
    except Exception:
        return []

@st.cache_data(ttl=120, show_spinner=False)
def hl_positions(addr):
    """A wallet's live perp positions + account value."""
    try:
        d = requests.post(HL_INFO, json={"type": "clearinghouseState", "user": addr}, timeout=12).json()
        acct = float(d.get("marginSummary", {}).get("accountValue", 0) or 0)
        out = []
        for p in d.get("assetPositions", []):
            pos = p.get("position", {})
            szi = float(pos.get("szi", 0) or 0)
            out.append({
                "coin": pos.get("coin", "?"),
                "szi": szi,
                "entryPx": float(pos.get("entryPx") or 0),
                "positionValue": float(pos.get("positionValue") or 0),
                "unrealizedPnl": float(pos.get("unrealizedPnl") or 0),
                "leverage": (pos.get("leverage") or {}).get("value"),
            })
        return acct, out
    except Exception:
        return None, []

@st.cache_data(ttl=300, show_spinner=False)
def hl_winrate(addr):
    """Win rate + realized PnL from a wallet's recent fills."""
    try:
        fills = requests.post(HL_INFO, json={"type": "userFills", "user": addr}, timeout=12).json()
        if not isinstance(fills, list):
            return None
        closed = [f for f in fills if float(f.get("closedPnl", 0) or 0) != 0]
        if not closed:
            return None
        wins = sum(1 for f in closed if float(f["closedPnl"]) > 0)
        return {
            "wins": wins,
            "total": len(closed),
            "winrate": wins / len(closed) * 100,
            "realized": sum(float(f["closedPnl"]) for f in closed),
            "lastFillMs": max((f.get("time", 0) for f in fills), default=0),
        }
    except Exception:
        return None

def _short(a):
    return a[:6] + "…" + a[-4:] if len(a) >= 10 else a

def render_whale_tracker():
    section_header("Whale tracker · Hyperliquid", "Follow the whales",
                   "Crypto is transparent — every wallet's trades are public on-chain. Build a watchlist of "
                   "big Hyperliquid traders (live positions, recent win rate, PnL), then arm phone alerts "
                   "so you're pinged the moment one makes a big move.")
    st.caption("Perps only · not affiliated with Hyperliquid · crypto is volatile and this is not financial advice.")

    follows = get_follows()

    # add a wallet by address (persisted in the URL, so it survives reload & is shareable)
    with st.form("add_whale", clear_on_submit=True):
        fc1, fc2 = st.columns([5, 1])
        addr = fc1.text_input("Track a wallet (0x… address)", placeholder="0x… paste any Hyperliquid wallet",
                              label_visibility="collapsed")
        submitted = fc2.form_submit_button("Follow")
    if submitted and addr:
        a = addr.strip().lower()
        if a.startswith("0x") and len(a) == 42:
            if a not in follows:
                follows.append(a); set_follows(follows); st.rerun()
        else:
            st.warning("That doesn't look like a valid 0x wallet address (should be 42 characters).")

    # ---- the whales you follow ----
    st.markdown("#### ⭐ My watchlist")
    if not follows:
        st.info("Your watchlist is empty. Paste a wallet above, or tap **Follow** on the leaderboard "
                "below. It's saved in this page's link — bookmark or share it to keep it.")
    else:
        now_ms = dt.datetime.now().timestamp() * 1000
        for a in follows:
            acct, pos = hl_positions(a)
            wr = hl_winrate(a)
            active = wr and (now_ms - wr["lastFillMs"] < 30 * 60 * 1000)
            h1, h2 = st.columns([5, 1])
            h1.markdown(f"**`{_short(a)}`**  " + ("🟢 **active in last 30 min**" if active else ""))
            if h2.button("Unfollow", key="unf_" + a):
                follows.remove(a); set_follows(follows); st.rerun()
            mc = st.columns(3)
            mc[0].metric("Account value", f"${acct:,.0f}" if acct else "—")
            mc[1].metric("Win rate (recent)", f"{wr['winrate']:.0f}%" if wr else "—",
                         f"{wr['wins']}/{wr['total']} trades" if wr else None)
            mc[2].metric("Realized PnL (recent)", f"${wr['realized']:,.0f}" if wr else "—")
            if pos:
                dfp = pd.DataFrame([{
                    "Coin": p["coin"],
                    "Side": "LONG" if p["szi"] > 0 else "SHORT",
                    "Size": abs(p["szi"]),
                    "Entry": p["entryPx"],
                    "Position $": p["positionValue"],
                    "Unreal. PnL": p["unrealizedPnl"],
                    "Lev": p["leverage"],
                } for p in pos])
                st.dataframe(dfp, hide_index=True, use_container_width=True, column_config={
                    "Entry": st.column_config.NumberColumn(format="$%.4g"),
                    "Position $": st.column_config.NumberColumn(format="$%.0f"),
                    "Unreal. PnL": st.column_config.NumberColumn(format="$%.0f"),
                    "Size": st.column_config.NumberColumn(format="%.4g"),
                })
            else:
                st.caption("No open positions right now (or data momentarily unavailable).")
            st.divider()

    # ---- turn the watchlist into phone alerts ----
    if follows:
        wl = [{"label": _short(a), "wallet": a, "min_usd": 500000} for a in follows]
        with st.expander("🔔 Get phone alerts when these whales trade"):
            st.markdown("Copy this into **`watchlist.json`** in your repo to arm phone alerts — "
                        "it's a one-time setup (see **ALERTS_SETUP.md**). `min_usd` is the smallest "
                        "trade that pings you; edit it per whale.")
            st.code(json.dumps(wl, indent=2), language="json")

    # ---- leaderboard: the whales moving size ----
    st.markdown("#### Top Hyperliquid traders")
    lb = hl_leaderboard()
    if not lb:
        st.info("Couldn't load the Hyperliquid leaderboard right now — it retries on refresh. "
                "You can still follow any wallet by pasting its address above.")
        return
    rank_by = st.radio("Rank by", ["Today's volume", "All-time PnL", "ROI"],
                       horizontal=True, key="wlrank",
                       help="'Today's volume' surfaces the whales actually moving size right now.")
    key = {"All-time PnL": "pnlAll", "Today's volume": "vlm", "ROI": "roiAll"}[rank_by]
    lb = sorted(lb, key=lambda x: x.get(key, 0), reverse=True)[:15]
    for r in lb:
        a = r["address"].lower()
        c = st.columns([3, 2.2, 1.8, 2.2, 1.6])
        c[0].markdown(f"`{_short(a)}`")
        c[1].markdown(f"PnL **${r['pnlAll']:,.0f}**")
        c[2].markdown(f"ROI {r['roiAll']*100:,.0f}%")
        c[3].markdown(f"Vol/day ${r['vlm']:,.0f}")
        if a in follows:
            c[4].markdown("✓ following")
        elif c[4].button("Follow", key="fol_" + a):
            follows.append(a); set_follows(follows); st.rerun()
    st.caption("Leaderboard comes from Hyperliquid's public stats endpoint and can lag or change. "
               "‘Win rate’ is computed from each wallet's recent fills (not its entire lifetime), so treat it as a guide.")


# ============================================================================
#  GAMBLE (Polymarket) — big whale bets on major macro / geopolitical markets
# ============================================================================
PM_GAMMA = "https://gamma-api.polymarket.com/markets"
PM_TRADES = "https://data-api.polymarket.com/trades"
MACRO_KEYWORDS = [
    "iran", "israel", "russia", "ukraine", "china", "taiwan", "war", "invade", "nuclear",
    "missile", "blockade", "ceasefire", "nato", "sanction", "north korea", "venezuela", "gaza",
    "fed", "rate", "interest", "inflation", "cpi", "recession", "gdp", "unemployment", "jobs",
    "tariff", "opec", "oil", "powell", "fomc", "debt", "shutdown", "trump", "biden", "putin",
    "election", "president", "presidential", "congress", "senate", "supreme court", "nobel",
]

def is_macro(text):
    t = (text or "").lower()
    return any(k in t for k in MACRO_KEYWORDS)

def mins_ago_ts(ts):
    return int((dt.datetime.now().timestamp() - ts) / 60)

@st.cache_data(ttl=300, show_spinner=False)
def pm_macro_markets():
    """Top macro / geopolitical prediction markets by volume, with current odds."""
    try:
        r = requests.get(PM_GAMMA, params={"closed": "false", "active": "true",
                         "limit": 250, "order": "volumeNum", "ascending": "false"},
                         headers={"User-Agent": "surge/1.0"}, timeout=15).json()
        out = []
        for m in r:
            if not is_macro(m.get("question")):
                continue
            prices = m.get("outcomePrices")
            if isinstance(prices, str):
                try: prices = json.loads(prices)
                except Exception: prices = []
            yes = float(prices[0]) if prices else None
            out.append({
                "question": m.get("question", ""),
                "yes": yes,
                "vol": float(m.get("volumeNum", 0) or 0),
                "endDate": (m.get("endDate") or "")[:10],
                "slug": m.get("slug", ""),
            })
        return out
    except Exception:
        return []

@st.cache_data(ttl=120, show_spinner=False)
def pm_big_bets(min_usd):
    """Recent large trades (>= min_usd) on macro markets — the whale bets."""
    try:
        r = requests.get(PM_TRADES, params={"limit": 500, "filterType": "CASH",
                         "filterAmount": int(min_usd)}, headers={"User-Agent": "surge/1.0"},
                         timeout=15).json()
        if not isinstance(r, list):
            return []
        out = []
        for t in r:
            if not is_macro(t.get("title")):
                continue
            usd = float(t.get("size", 0)) * float(t.get("price", 0))
            out.append({
                "usd": usd,
                "side": t.get("side", ""),
                "outcome": t.get("outcome", ""),
                "title": t.get("title", ""),
                "price": float(t.get("price", 0)),
                "wallet": t.get("proxyWallet", ""),
                "name": t.get("name") or t.get("pseudonym") or "",
                "eventSlug": t.get("eventSlug", ""),
                "mins": mins_ago_ts(t.get("timestamp", 0)),
            })
        out.sort(key=lambda x: x["mins"])   # most recent first
        return out
    except Exception:
        return []

def render_gamble():
    section_header("Gamble · Polymarket", "Big money on big macro",
                   "Prediction markets are transparent — the big bets and the wallets behind them are public. "
                   "See whales putting real size on major macro & geopolitical questions.")
    st.caption("Real-money betting · availability varies by jurisdiction · not financial or betting advice.")

    top = st.columns([3, 2])
    query = top[0].text_input("Focus on a topic (optional)", placeholder="e.g. Iran, Fed, election",
                              label_visibility="collapsed")
    min_usd = top[1].selectbox("Minimum bet size", [1000, 5000, 10000, 25000, 50000],
                               index=2, format_func=lambda v: f"≥ ${v:,}")

    def match(text):
        return (not query) or (query.strip().lower() in (text or "").lower())

    # ---- big macro bets feed (the "notifications") ----
    bets = [b for b in pm_big_bets(min_usd) if match(b["title"])]
    st.markdown("#### 🚨 Big macro bets — live")
    if not bets:
        st.info("No macro bets above that size in the recent feed"
                + (f" matching “{query}”." if query else ".")
                + " Lower the minimum, clear the topic, or check back — big bets come in bursts.")
    else:
        # banner: biggest bet in the last hour
        recent = [b for b in bets if b["mins"] <= 60]
        if recent:
            top_bet = max(recent, key=lambda x: x["usd"])
            st.warning(f"🐋 Biggest bet in the last hour: **${top_bet['usd']:,.0f}** on "
                       f"**{top_bet['side']} {top_bet['outcome']}** — {top_bet['title']}", icon="🚨")
        for b in bets[:25]:
            fresh = "🟢 " if b["mins"] <= 30 else ""
            c = st.columns([2.4, 5, 1.8, 2])
            c[0].markdown(f"{fresh}**${b['usd']:,.0f}**")
            mkt = (f"[{b['title'][:70]}](https://polymarket.com/event/{b['eventSlug']})"
                   if b["eventSlug"] else b["title"][:70])
            c[1].markdown(f"{b['side']} **{b['outcome']}** · {mkt}")
            c[2].markdown(f"@ {b['price']*100:.0f}¢")
            wlink = f"[{b['name'][:12] or b['wallet'][:8]}](https://polymarket.com/profile/{b['wallet']})"
            c[3].markdown(f"{wlink} · {ago(b['mins'])}")

    # ---- macro markets to watch ----
    st.markdown("#### Macro markets to watch")
    mkts = [m for m in pm_macro_markets() if match(m["question"])]
    if not mkts:
        st.info("No macro markets matched." if query else "Couldn't load markets right now — retries on refresh.")
    else:
        df = pd.DataFrame([{
            "Market": m["question"][:70],
            "YES odds": (m["yes"] * 100) if m["yes"] is not None else None,
            "Volume": f"${m['vol']/1e6:.1f}M" if m["vol"] >= 1e6 else f"${m['vol']/1e3:.0f}K",
            "Closes": m["endDate"],
        } for m in mkts[:15]])
        st.dataframe(df, hide_index=True, use_container_width=True, column_config={
            "Market": st.column_config.TextColumn(width="large"),
            "YES odds": st.column_config.NumberColumn("YES odds", format="%.0f%%",
                          help="Market-implied probability the answer is YES."),
            "Volume": st.column_config.TextColumn(help="Total money traded on this market."),
        })
    st.caption("Odds are the market-implied probability. Data from Polymarket's public API; it can lag or change.")


def render_sp_spikes():
    section_header("S&P 500 · Volume radar", "Where the volume is spiking",
                   "Every S&P 500 name trading unusually heavy right now — shown automatically, no filters. "
                   "If one slice of the wheel dominates, the spike is sector-wide, not just one stock.")
    market_pulse_strip()

    sens = st.select_slider("Spike sensitivity — relative volume ≥",
                            options=[1.5, 2.0, 2.5, 3.0, 4.0, 5.0], value=2.0)
    with st.spinner("Scanning all 500 S&P names for volume spikes…"):
        df = get_sp_spikes(sens)

    if df is None:
        st.info("Couldn't load S&P data right now (a brief Yahoo hiccup) — it retries on the next refresh.")
        return
    if df.empty:
        st.success(f"😌 No unusual S&P 500 volume right now at ≥ {sens:g}× — the index is trading at a normal pace. "
                   "Lower the sensitivity to see milder moves.")
        return

    up = int((df["chg"] > 0).sum()); down = int((df["chg"] <= 0).sum())
    sec_sum = df.groupby("sector")["excess"].sum().sort_values(ascending=False)
    top_sector = sec_sum.index[0]
    share = sec_sum.iloc[0] / sec_sum.sum() * 100 if sec_sum.sum() else 0

    m = st.columns(3)
    m[0].metric("S&P names spiking", len(df))
    m[1].metric("Direction", f"{up} up · {down} down")
    m[2].metric("Hottest sector", top_sector, f"{share:.0f}% of the spike")

    left, right = st.columns([1, 1.5])
    with left:
        st.caption("Share of the volume spike by sector")
        sec = sec_sum.reset_index()
        sec = sec[sec["excess"] > 0]
        donut = (alt.Chart(sec)
                 .mark_arc(innerRadius=58, cornerRadius=3, stroke="#0b0e15", strokeWidth=2)
                 .encode(
                     theta=alt.Theta("excess:Q", stack=True),
                     color=alt.Color("sector:N", legend=alt.Legend(orient="bottom", title=None, columns=2),
                                     scale=alt.Scale(scheme="tableau20")),
                     tooltip=[alt.Tooltip("sector:N", title="Sector"),
                              alt.Tooltip("excess:Q", title="Extra $ volume", format="$,.0f")])
                 .properties(height=300))
        st.altair_chart(donut, use_container_width=True)
    with right:
        show = df.sort_values("rvol", ascending=False)
        disp = pd.DataFrame({
            "Ticker": show["sym"], "Sector": show["sector"],
            "Price": show["price"], "% Chg": show["chg"], "R.Vol": show["rvol"],
            "Volume": show["vol"].apply(fmt_vol),
        })
        cfg_sp = {
            "Sector": st.column_config.TextColumn(width="small"),
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "% Chg": st.column_config.NumberColumn(format="%.1f%%"),
            "R.Vol": st.column_config.NumberColumn("R.Vol", format="%.1f×",
                        help="Today's volume vs. the stock's 20-day average. Higher = bigger spike."),
        }
        try:
            st.dataframe(style_board(disp), hide_index=True, use_container_width=True,
                         height=330, column_config=cfg_sp)
        except Exception:
            st.dataframe(disp, hide_index=True, use_container_width=True, height=330, column_config=cfg_sp)
    st.caption("Spike = today's volume running well above the stock's 20-day average. Data via yfinance · not financial advice.")


# ----------------------------------------------------------------------------
# LEFT SIDEBAR = brand + section navigation + status
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        "<div class='beacon-row'><div class='beacon'></div>"
        "<div><div class='wordmark'>SUR<span>GE</span></div>"
        "<div class='tagline'>what's in play</div></div></div>",
        unsafe_allow_html=True)
    st.markdown("<div class='navlabel'>Sections</div>", unsafe_allow_html=True)
    section = st.radio("Sections",
                       ["📈 Stock scanner", "🔥 S&P Spikes", "🐋 Whale tracker", "🎲 Gamble"],
                       label_visibility="collapsed")
    st.markdown("<hr style='margin:16px 0 12px;border-color:#262e3d'>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:12px;color:#6b7690;line-height:1.7'>"
                f"updated {et_now().strftime('%I:%M %p ET')}<br>auto-refresh · 2 min</div>",
                unsafe_allow_html=True)
    st.caption("Data: yfinance · Finnhub · Hyperliquid · Polymarket. Not financial advice.")

if section.startswith("🔥"):
    render_sp_spikes()
    st.stop()
if section.startswith("🐋"):
    render_whale_tracker()
    st.stop()
if section.startswith("🎲"):
    render_gamble()
    st.stop()

# ---- STOCK SCANNER ----
section_header("Stock scanner", "Stocks in play",
               "Every name below clears all three signals at once — a real move, on real volume, "
               "with a real reason behind it.")
market_pulse_strip()

# on-page filters — simple, always visible
st.markdown("<div class='filterhead'>Filters</div>", unsafe_allow_html=True)
f1, f2, f3, f4 = st.columns([2.3, 1.7, 1.5, 1.1])
chg_min, chg_max = f1.slider("Gain today (%)", 0.0, 30.0, (5.0, 10.0), 0.5,
                             help="How far up on the day. The classic momentum setup is +5% to +10%.")
rvol_min = f2.slider("Volume surge (×)", 1.0, 10.0, 2.0, 0.5,
                     help="How much heavier than a normal day. 2× = twice the usual pace.")
news_hours = f3.slider("News within (hrs)", 1, 48, 8, help="Only count news this fresh.")
top_n = f4.slider("Show", 5, 40, 20, help="How many names to list.")
g1, g2 = st.columns([1.5, 3.5])
require_news = g1.toggle("Require fresh news", value=True)
with g2.expander("More filters"):
    price_min, price_max = st.slider("Price per share ($)", 0.0, 500.0, (1.0, 200.0), 1.0)

# chips summarise the active filters in plain language
st.markdown(
    "<div class='chips'>"
    f"<span class='chip'><span class='k' style='background:#2ecb8f'>1</span> Up today "
    f"<span class='v'>{chg_min:.0f}–{chg_max:.0f}%</span></span>"
    f"<span class='chip'><span class='k' style='background:#f0a63a'>2</span> Heavy volume "
    f"<span class='v'>RVOL ≥ {rvol_min:.1f}×</span></span>"
    f"<span class='chip'><span class='k' style='background:#6b74e8'>3</span> "
    + (f"Fresh news <span class='v'>≤ {news_hours}h</span>" if require_news else "News optional")
    + "</span></div>",
    unsafe_allow_html=True)

if not FINNHUB_KEY:
    st.warning("No Finnhub key set — news is off. Add FINNHUB_KEY in app settings → Secrets. "
               "(See DEPLOY_GUIDE.md step 4.)", icon="🔑")

# ---- friendly guide for first-time visitors ----
if st.checkbox("👋 New here? Tick this box for a 30-second guide to reading the board"):
    st.markdown("""
**What this is.** Surge scans the market and shows stocks that are *in play right now* —
meaning something just happened and traders are piling in. It updates itself every couple of minutes.

**Every stock here passes three tests at once:**
1. **Up today, +5% to +10%** — it's already moving, but hasn't gone parabolic.
2. **Heavy volume (RVOL ≥ 2×)** — it's trading at least twice its normal pace, so demand is real, not a fluke.
3. **Fresh news** — there's an actual reason behind the move (earnings, a deal, an approval).

**Reading a row, left to right:**
- **Price** – what one share costs right now.
- **% Chg** – how much it's up today.
- **R.Vol** – "relative volume." *2× = twice the usual trading.* Higher = more heat.
- **Volume** – total shares traded today.
- **Float** – how many shares are actually available to trade. A **low float** can move fast and hard.
- **Target** – how far the average Wall-Street analyst target sits above today's price *(an opinion, not a promise)*.
- **Why it's moving** – the headline behind the move.

**Want the full story on one stock?** Use the **🔍 Inspect a ticker** box below the table — you'll get a
live 1-minute chart, its volume minute-by-minute (pre-market, regular hours, and after-hours), the news, and the analyst price target.

**Three session tabs** — **🌅 Pre-market** (4:00–9:30 AM ET), **🔔 Live market** (9:30 AM–4:00 PM ET),
and **🌙 After-hours** (4:00–8:00 PM ET). Each shows what's moving *in that session*, with its own
volume and news. The 🟢 marks whichever session is happening right now; the others fill in during their hours.

**The S&P 500 / Outside toggle** lets you split big, well-known companies from smaller, faster-moving ones.

**Tweak it to your taste** with the settings panel on the left (arrow at top-left): change how many
stocks show, the % range, how much volume counts, and the price range.

> ⚠️ **Important:** This is a *starting point for research, not advice.* A stock that's already up can
> reverse just as fast. Surge points you at what's active — what you do next is your call.
""")

# ----------------------------------------------------------------------------
# SCAN THE UNIVERSE ONCE, THEN SPLIT INTO SESSIONS
# ----------------------------------------------------------------------------
with st.spinner("Scanning the market…"):
    universe = load_universe()

if not universe:
    st.warning("The movers list is thin right now — common outside U.S. market hours. The "
               "Pre-market / Live / After-hours tabs below stay put and fill in during the session.",
               icon="🕒")
    universe = []   # keep going so the session tabs always render

# ---- S&P 500 filter (applies to all three session tabs) ----
n_sp = sum(1 for d in universe if d.get("sp500"))
view = st.radio(
    "Market",
    [f"All ({len(universe)})", f"S&P 500 ({n_sp})", f"Outside S&P 500 ({len(universe)-n_sp})"],
    horizontal=True, label_visibility="collapsed",
)
stocks_f = apply_market_filter(universe, view)

def float_tag(f):
    if not f: return ""
    if f < 20e6:  return "<span class='tag low'>Low float</span>"
    if f < 100e6: return "<span class='tag mid'>Mid</span>"
    return "<span class='tag mid'>Large</span>"

shown = {}   # every ticker displayed across the tabs → feeds the inspector below

def board_table(rows, mode):
    """Render the board with Streamlit's NATIVE table (sortable, header tooltips, can't
    render as raw HTML). mode 'regular' = today's numbers; 'session' = pre/after-hours."""
    data = []
    for d in rows:
        up = None
        if d.get("target") and d.get("price"):
            up = (d["target"] - d["price"]) / d["price"] * 100
        news = d.get("news")
        price = d["s_price"] if mode == "session" else d["price"]
        chg   = d["s_chg"]   if mode == "session" else d["chg"]
        vol   = d.get("s_vol") if mode == "session" else d["vol"]
        row = {
            "Ticker": d["sym"] + ("  ·S&P" if d.get("sp500") else ""),
            "Company": d["name"][:28],
            "Price": price,
            "% Chg": chg,
        }
        if mode == "regular":
            row["R.Vol"] = d["rvol"]
        row["Volume"] = fmt_vol(vol)
        row["Float"] = fmt_float(d["float"])
        row["Target"] = up
        row["Why it's moving"] = news["headline"] if news else "—"
        data.append(row)
        shown[d["sym"]] = d

    df = pd.DataFrame(data)
    vol_help = ("Shares traded so far today." if mode == "regular"
                else "Shares traded during this session only (pre-market or after-hours).")
    cfg = {
        "Ticker":  st.column_config.TextColumn("Ticker",
                     help="Ticker symbol. ·S&P marks a member of the S&P 500."),
        "Company": st.column_config.TextColumn("Company"),
        "Price":   st.column_config.NumberColumn("Price", format="$%.2f",
                     help="Share price in this session."),
        "% Chg":   st.column_config.NumberColumn("% Chg", format="%.1f%%",
                     help="How far the price has moved. Pre-market is vs. yesterday's close; "
                          "after-hours is vs. the 4 PM close."),
        "Volume":  st.column_config.TextColumn("Volume", help=vol_help),
        "Float":   st.column_config.TextColumn("Float",
                     help="Float — shares actually available to trade. A low float can move fast and hard."),
        "Target":  st.column_config.NumberColumn("Target ▲", format="+%.0f%%",
                     help="Upside to the average analyst price target. An opinion, not a guarantee."),
        "Why it's moving": st.column_config.TextColumn("Why it's moving", width="large",
                     help="The most recent news headline driving the move."),
    }
    if mode == "regular":
        cfg["R.Vol"] = st.column_config.NumberColumn("R.Vol", format="%.1f×",
                         help="Relative Volume — today's trading vs. a normal day. 2× = twice the usual.")
    h = min(len(df) * 36 + 42, 760)
    try:
        st.dataframe(style_board(df), column_config=cfg, hide_index=True,
                     use_container_width=True, height=h)
    except Exception:
        st.dataframe(df, column_config=cfg, hide_index=True, use_container_width=True, height=h)

sess = current_session()
def dot(s): return " 🟢" if s == sess else ""
tab_pre, tab_live, tab_post = st.tabs(
    [f"🌅 Pre-market{dot('pre')}", f"🔔 Live market{dot('live')}", f"🌙 After-hours{dot('post')}"])

with tab_pre:
    st.caption("Pre-market · 4:00–9:30 AM ET · moves measured vs. yesterday's close"
               + ("  ·  **live now**" if sess == "pre" else ""))
    rows = scan_session(stocks_f, "pre")
    if rows:
        board_table(rows, "session")
    else:
        st.info("No pre-market movers pass your filters right now. Pre-market data starts filling in "
                "around 4 AM ET — during the regular day this tab is usually empty.")

with tab_live:
    st.caption("Regular hours · 9:30 AM–4:00 PM ET"
               + ("  ·  **live now**" if sess == "live" else ""))
    rows = scan_regular(stocks_f)
    if rows:
        board_table(rows, "regular")
    else:
        st.info("No stocks pass all three filters right now. Widen the % range, lower relative volume, "
                "or turn off 'require news' in the sidebar — see the note below on why the list can be short.")

with tab_post:
    st.caption("After-hours · 4:00–8:00 PM ET · moves measured vs. the 4 PM close"
               + ("  ·  **live now**" if sess == "post" else ""))
    rows = scan_session(stocks_f, "post")
    if rows:
        board_table(rows, "session")
    else:
        st.info("No after-hours movers pass your filters right now. After-hours data starts filling in "
                "after 4 PM ET — before then this tab is usually empty.")

st.caption("💡 Hover any column header for what it means. The 🟢 marks the session that's live right now.")

# why the list may be short
if st.checkbox("❓ Only seeing a few names? Tick this box to learn why (and how to see more)"):
    st.markdown("""
That's usually **working as intended** — the whole point is a *short, high-quality* list. A stock only
appears if it clears **all three** filters at once (up 5–10%, ≥2× volume, *and* fresh news), and at any
given moment only a handful of the day's ~thousands of stocks do. Two or three names is normal; sometimes
zero, especially near the open/close or outside U.S. hours.

**To see more, open the sidebar (arrow, top-left) and:**
- turn **off** "Require a fresh news catalyst" (the news filter is the strictest one),
- widen the **% change** range (e.g. 3% to 20%),
- lower **min relative volume** (e.g. 1.5×),
- raise **"Show top N by volume."**

Loosening trades quality for quantity — your call.""")

if not shown:
    st.stop()

# ----------------------------------------------------------------------------
# PER-TICKER DETAIL  (pick one to inspect)
# ----------------------------------------------------------------------------
st.markdown("---")
syms = list(shown.keys())
pick = st.selectbox("🔍 Inspect a ticker (live chart · minute volume · news · price target)", syms, index=0)
d = shown[pick]

sp_tag = ("<b style='color:#2ecb8f'>S&P 500</b>" if d.get("sp500")
          else "<span style='color:#a6b0c3'>Outside S&P 500</span>")
st.markdown(f"## {d['sym']}  "
            f"<span style='font-size:15px;color:#6b7690'>{d['name']} · {d['sector']} · {sp_tag}</span>",
            unsafe_allow_html=True)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Price", f"${d['price']:.2f}", f"{d['chg']:.1f}%")
m2.metric("Rel. volume", f"{d['rvol']:.1f}×")
m3.metric("Volume", fmt_vol(d["vol"]))
m4.metric("Float", fmt_float(d["float"]))

tab_ov, tab_chart, tab_vol, tab_tgt = st.tabs(["Overview", "Chart", "Volume", "Price target"])

# ---- Overview / news ----
with tab_ov:
    news = d.get("news")
    if news:
        st.markdown(f"**The catalyst — {news['source']} · {ago(news['mins'])}**")
        st.markdown(f"#### {news['headline']}")
        # a plain-language read on why volume is moving
        st.markdown(
            f"<div style='background:#141924;border-left:3px solid #f0a63a;border-radius:8px;"
            f"padding:12px 14px;margin:6px 0 12px;color:#c9d2e0;font-size:14px'>"
            f"The move started when this story broke ~{ago(news['mins'])}, and volume immediately "
            f"jumped to <b>{d['rvol']:.1f}× normal</b>. That's the market repricing "
            f"<b>{d['name']}</b> on the news — demand outpacing supply, not random drift.</div>",
            unsafe_allow_html=True)
        if news.get("summary"):
            st.write(news["summary"])
        if news.get("url"):
            st.markdown(f"[Read full story →]({news['url']})")
        # deeper: more recent coverage — plain markdown so the links are clickable
        more = news.get("more") or []
        if more:
            st.markdown(f"**More coverage** · {news.get('count', len(more))} recent stories")
            for m in more:
                if m.get("url"):
                    st.markdown(f"- [{m['headline']}]({m['url']})  —  {m['source']} · {ago(m['mins'])}")
                else:
                    st.markdown(f"- {m['headline']}  —  {m['source']} · {ago(m['mins'])}")
    else:
        st.info("No fresh headline found in the news window for this name. "
                "Widen the news window in the sidebar to see older stories.")

# ---- Chart: live TradingView 1-minute ----
with tab_chart:
    st.caption("Live interactive 1-minute chart · powered by TradingView")
    tv = f"""
    <div class="tradingview-widget-container" style="height:460px">
      <div id="tv_{d['sym']}" style="height:460px"></div>
      <script src="https://s3.tradingview.com/tv.js"></script>
      <script>
      new TradingView.widget({{
        "autosize": true, "symbol": "{d['sym']}", "interval": "1",
        "timezone": "America/New_York", "theme": "dark", "style": "1",
        "locale": "en", "hide_top_toolbar": false, "hide_legend": false,
        "allow_symbol_change": true, "container_id": "tv_{d['sym']}"
      }});
      </script>
    </div>"""
    components.html(tv, height=470)
    st.caption("If the chart is blank, TradingView may need an exchange prefix "
               "(e.g. NASDAQ:AAPL) — use the symbol box on the chart itself.")

# ---- Volume: session split + per-minute chart ----
with tab_vol:
    h = get_minutes(d["sym"])
    if h is None or h.empty:
        st.info("Minute data isn't available for this ticker right now.")
    else:
        t = h.index.time
        def sess(x):
            if x < dt.time(9, 30): return "Pre-market"
            if x < dt.time(16, 0): return "Regular"
            return "Post-market"
        h = h.copy()
        h["Session"] = [sess(x) for x in t]
        totals = h.groupby("Session")["Volume"].sum()
        tot = totals.sum() or 1
        s1, s2, s3 = st.columns(3)
        for col, name in [(s1, "Pre-market"), (s2, "Regular"), (s3, "Post-market")]:
            v = int(totals.get(name, 0))
            col.metric(name, fmt_vol(v), f"{v/tot*100:.0f}% of day")

        st.markdown("**Volume per minute** — watch the ramp; a spike is demand outpacing supply *now*.")
        st.bar_chart(h["Volume"], height=240, color="#2ecb8f")

# ---- Price target: real analyst consensus ----
with tab_tgt:
    if not d["target"] or not d["n_analysts"]:
        st.info("No analyst price-target coverage for this ticker.")
    else:
        up = (d["target"] - d["price"]) / d["price"] * 100
        st.markdown(f"<div style='text-align:center'>"
                    f"<div style='font-size:40px;font-weight:700;color:{'#2ecb8f' if up>=0 else '#f0685a'};"
                    f"font-family:IBM Plex Mono,monospace'>{'+' if up>=0 else ''}{up:.0f}%</div>"
                    f"<div style='color:#6b7690'>upside to consensus target "
                    f"<b class='mono'>${d['target']:.2f}</b> · {d['n_analysts']} analysts</div></div>",
                    unsafe_allow_html=True)
        lo, hi = d.get("target_lo"), d.get("target_hi")
        if lo and hi and hi > lo:
            pos = max(0, min(100, (d["price"] - lo) / (hi - lo) * 100))
            tpos = max(0, min(100, (d["target"] - lo) / (hi - lo) * 100))
            st.markdown(f"""
            <div style='margin:26px 4px 6px;position:relative;height:8px;border-radius:5px;
                 background:linear-gradient(90deg,#3a1c1a,#212836,#123027)'>
              <div style='position:absolute;left:{pos:.0f}%;top:-6px;width:12px;height:12px;border-radius:50%;
                   background:#e9edf5;border:2px solid #0c0f16;transform:translateX(-50%)'></div>
              <div style='position:absolute;left:{tpos:.0f}%;top:-6px;width:12px;height:12px;border-radius:50%;
                   background:#2ecb8f;border:2px solid #0c0f16;transform:translateX(-50%)'></div>
            </div>
            <div style='display:flex;justify-content:space-between;font-size:11px;color:#6b7690;
                 font-family:IBM Plex Mono,monospace'><span>low ${lo:.2f}</span>
                 <span>⚪ now &nbsp; 🟢 target</span><span>high ${hi:.2f}</span></div>
            """, unsafe_allow_html=True)
        st.warning("These are **real published analyst targets** — not a prediction of where the "
                   "news will take the stock. Targets are opinions, often lag fast-moving news, and "
                   "are frequently wrong. Never a substitute for your own research.", icon="⚠️")

st.caption("Surge surfaces candidates · not financial advice · a stock already up on the day can reverse.")
