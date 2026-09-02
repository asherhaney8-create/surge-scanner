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
import pandas as pd
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
:root { --accent:#f0a63a; --up:#2ecb8f; --down:#f0685a; }
.stApp { background:#0c0f16; }
#MainMenu, footer {visibility:hidden;}  /* keep the header so the sidebar arrow stays visible */
.block-container{padding-top:1.2rem; max-width:1200px;}
h1,h2,h3,h4,p,span,div,label { color:#e9edf5; font-family:"IBM Plex Sans",system-ui,sans-serif; }
.mono, .mono * { font-family:"IBM Plex Mono",monospace; }
.beacon-row{display:flex;align-items:center;gap:12px;margin-bottom:2px;}
.beacon{width:34px;height:34px;border-radius:10px;background:radial-gradient(circle at 50% 38%,#f0a63a,#b06f16);
        display:grid;place-items:center;box-shadow:0 0 0 4px #3a2c14;}
.beacon::after{content:"";width:9px;height:9px;border-radius:50%;background:#fff;}
.wordmark{font-family:"Archivo",sans-serif;font-weight:800;font-size:24px;letter-spacing:-.5px;}
.wordmark span{color:#f0a63a;}
.tagline{font-size:12px;color:#6b7690;margin-top:-2px;}
.chips{display:flex;gap:9px;flex-wrap:wrap;margin:10px 0 6px;}
.chip{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;font-size:12.5px;
      font-weight:600;background:#1a202d;border:1px solid #262e3d;color:#e9edf5;}
.chip .k{width:19px;height:19px;border-radius:50%;display:grid;place-items:center;font-size:11px;color:#fff;}
.demo{background:#3a2c14;border:1px solid #f0a63a;color:#f4bd63;font-weight:700;font-size:11px;
      padding:4px 9px;border-radius:6px;letter-spacing:.5px;}
/* scanner table */
table.surge{width:100%;border-collapse:collapse;font-size:13.5px;}
table.surge th{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:#6b7690;text-align:right;
               padding:10px 12px;border-bottom:1px solid #262e3d;}
table.surge th.l,table.surge td.l{text-align:left;}
table.surge td{padding:10px 12px;border-bottom:1px solid #1a202d;font-family:"IBM Plex Mono",monospace;}
table.surge tr:hover td{background:#141924;}
table.surge th[title]{cursor:help;border-bottom:1px dotted #37415a;}
.sym-t{font-weight:600;font-size:14px;color:#e9edf5;}
.sym-n{font-size:11px;color:#6b7690;font-family:"IBM Plex Sans",sans-serif;}
.up{color:#2ecb8f;} .down{color:#f0685a;}
.tag{font-size:9.5px;font-weight:700;letter-spacing:.4px;padding:2px 6px;border-radius:5px;font-family:"IBM Plex Sans",sans-serif;}
.tag.low{color:#f4bd63;background:#3a2c14;} .tag.mid{color:#a6b0c3;background:#212836;}
.cat{text-align:left!important;font-family:"IBM Plex Sans",sans-serif!important;color:#c9d2e0;max-width:320px;}
.cat small{color:#6b7690;}
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# SIDEBAR — tunable filters (this is your control panel)
# ----------------------------------------------------------------------------
st.sidebar.markdown("### ⚙️ Scan settings")
chg_min = st.sidebar.slider("Min % change today", 0.0, 20.0, 5.0, 0.5)
chg_max = st.sidebar.slider("Max % change today", 0.0, 30.0, 10.0, 0.5)
rvol_min = st.sidebar.slider("Min relative volume (×)", 1.0, 10.0, 2.0, 0.5)
price_min, price_max = st.sidebar.slider("Price range ($)", 0.0, 500.0, (1.0, 200.0), 1.0)
news_hours = st.sidebar.slider("News must be within (hours)", 1, 48, 8)
require_news = st.sidebar.checkbox("Require a fresh news catalyst", value=True)
top_n = st.sidebar.slider("Show top N by volume", 5, 40, 20)
st.sidebar.caption("Change a setting and the board updates instantly.")
st.sidebar.markdown("---")
st.sidebar.caption("Auto-refreshes every 2 minutes. Data: yfinance + Finnhub. "
                   "Not financial advice.")

# auto-refresh every 120s
if st_autorefresh:
    st_autorefresh(interval=120 * 1000, key="surge_refresh")

FINNHUB_KEY = st.secrets.get("FINNHUB_KEY", "") if hasattr(st, "secrets") else ""

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
def get_sp500():
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        syms = set(tables[0]["Symbol"].astype(str).str.replace(".", "-", regex=False))
        if len(syms) > 400:
            return syms
    except Exception:
        pass
    return SP500_FALLBACK

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

# ----------------------------------------------------------------------------
# RUN THE SCAN
# ----------------------------------------------------------------------------
def fmt_vol(v):
    if v is None: return "—"
    return f"{v/1e6:.1f}M" if v >= 1e6 else f"{v/1e3:.0f}K"

def fmt_float(f):
    if not f: return "—"
    return f"{f/1e6:.1f}M"

def ago(m):
    return f"{m}m ago" if m < 60 else f"{m//60}h {m%60}m ago"

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

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("""
    <div class="beacon-row"><div class="beacon"></div>
      <div><div class="wordmark">SUR<span>GE</span></div>
      <div class="tagline">stocks in play, right now</div></div></div>
    <div class="chips">
      <span class="chip"><span class="k" style="background:#2ecb8f">1</span> Up today {a:.0f}–{b:.0f}%</span>
      <span class="chip"><span class="k" style="background:#f0a63a">2</span> RVOL ≥ {r:.1f}×</span>
      <span class="chip"><span class="k" style="background:#6b74e8">3</span> {n}</span>
    </div>""".format(a=chg_min, b=chg_max, r=rvol_min,
                     n=("Fresh news ≤ %dh" % news_hours) if require_news else "News optional"),
    unsafe_allow_html=True)
with c2:
    now = dt.datetime.now().strftime("%I:%M %p")
    st.markdown(f"<div style='text-align:right;color:#6b7690;font-size:12px;margin-top:8px'>"
                f"updated {now}<br>auto-refresh: 2 min</div>", unsafe_allow_html=True)

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
    st.info("Couldn't load any movers right now — outside U.S. hours the lists thin out, or "
            "Yahoo is briefly unavailable. It retries on the next refresh.")
    st.stop()

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
    """mode 'regular' shows today's numbers; mode 'session' shows pre/after-hours numbers."""
    body = ""
    for i, d in enumerate(rows, 1):
        up = d["target"] and d["price"] and ((d["target"] - d["price"]) / d["price"] * 100)
        up_html = (f"<span class='up'>+{up:.0f}%</span>" if up and up >= 0
                   else (f"<span class='down'>{up:.0f}%</span>" if up else "—"))
        news = d.get("news")
        cat = (f"{news['headline'][:120]}<br><small>{news['source']} · {ago(news['mins'])}</small>"
               if news else "<small style='color:#6b7690'>no fresh headline</small>")
        sp_mark = " <span class='tag mid'>S&P</span>" if d.get("sp500") else ""
        price = d["s_price"] if mode == "session" else d["price"]
        chg   = d["s_chg"]   if mode == "session" else d["chg"]
        vol   = d.get("s_vol") if mode == "session" else d["vol"]
        rvol_cell = f"<td>{d['rvol']:.1f}×</td>" if mode == "regular" else ""
        body += f"""<tr>
          <td class='l' style='color:#6b7690'>{i}</td>
          <td class='l'><span class='sym-t'>{d['sym']}</span>{sp_mark}<br><span class='sym-n'>{d['name'][:26]}</span></td>
          <td>${price:.2f}</td>
          <td class='up'>▲ {chg:.1f}%</td>
          {rvol_cell}
          <td>{fmt_vol(vol)}</td>
          <td>{fmt_float(d['float'])} {float_tag(d['float'])}</td>
          <td>{up_html}</td>
          <td class='cat'>{cat}</td>
        </tr>"""
        shown[d["sym"]] = d
    if mode == "regular":
        vol_h = 'title="Total shares traded so far today.">Volume'
        rvol_h = ('<th title="Relative Volume — today\'s trading vs. a normal day. '
                  '2x means twice the usual: demand outpacing supply.">R.Vol</th>')
    else:
        vol_h = 'title="Shares traded during this session only (pre-market or after-hours).">Session Vol'
        rvol_h = ''
    st.markdown(f"""<table class='surge'>
      <tr>
        <th class='l'>#</th>
        <th class='l' title="The stock's ticker symbol and company name.">Ticker</th>
        <th title="Share price in this session.">Price</th>
        <th title="How far the price has moved. Pre-market is vs. yesterday's close; after-hours is vs. the 4 PM close.">% Chg</th>
        {rvol_h}
        <th {vol_h}</th>
        <th title="Float — shares actually available to trade. A low float can move fast and hard.">Float</th>
        <th title="How far the average analyst price target sits above today's price. An opinion, not a guarantee.">Target</th>
        <th class='l' title="The most recent news headline driving the move.">Why it's moving</th>
      </tr>
      {body}</table>""", unsafe_allow_html=True)

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
      
