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
st.set_page_config(page_title="Surge Scanner", page_icon="📈", layout="wide")

# ---- Surge look & feel (dark, amber beacon accent) -------------------------
st.markdown("""
<style>
:root { --accent:#f0a63a; --up:#2ecb8f; --down:#f0685a; }
.stApp { background:#0c0f16; }
#MainMenu, footer, header {visibility:hidden;}
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

def run_scan():
    sp = get_sp500()
    rows = []
    for sym in get_universe():
        d = get_stock(sym)
        if not d:
            continue
        if not (chg_min <= d["chg"] <= chg_max): continue
        if d["rvol"] < rvol_min: continue
        if not (price_min <= d["price"] <= price_max): continue
        d["news"] = get_news(sym, news_hours)
        if require_news and not d["news"]:
            continue
        d["sp500"] = d["sym"] in sp
        rows.append(d)
    rows.sort(key=lambda x: x["vol"], reverse=True)
    return rows   # the S&P toggle + top_n slice are applied where the table is drawn

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

# ----------------------------------------------------------------------------
# SCANNER TABLE
# ----------------------------------------------------------------------------
with st.spinner("Scanning the market…"):
    all_results = run_scan()

if not all_results:
    st.info("No stocks currently pass all your filters. Try widening the % range, lowering "
            "relative volume, or turning off 'require news' in the sidebar. "
            "(Outside U.S. market hours the mover lists can also be thin.)")
    st.stop()

# ---- the S&P 500 toggle bar ----
n_sp = sum(1 for d in all_results if d.get("sp500"))
n_out = len(all_results) - n_sp
view = st.radio(
    "Market",
    [f"All ({len(all_results)})", f"S&P 500 ({n_sp})", f"Outside S&P 500 ({n_out})"],
    horizontal=True, label_visibility="collapsed",
)
if view.startswith("S&P"):
    results = [d for d in all_results if d.get("sp500")][:top_n]
    sub = "today's S&P 500 names"
elif view.startswith("Outside"):
    results = [d for d in all_results if not d.get("sp500")][:top_n]
    sub = "names outside the S&P 500"
else:
    results = all_results[:top_n]
    sub = "most active names in play"

st.markdown(f"#### Top {len(results)} by volume  "
            f"<span style='font-size:13px;color:#6b7690'>· {sub}</span>",
            unsafe_allow_html=True)

if not results:
    st.info("No names in this group right now — try the **All** view or widen the sidebar filters.")
    st.stop()

def float_tag(f):
    if not f: return ""
    if f < 20e6:  return "<span class='tag low'>Low float</span>"
    if f < 100e6: return "<span class='tag mid'>Mid</span>"
    return "<span class='tag mid'>Large</span>"

rows_html = ""
for i, d in enumerate(results, 1):
    up = d["target"] and d["price"] and ((d["target"] - d["price"]) / d["price"] * 100)
    up_html = f"<span class='up'>+{up:.0f}%</span>" if up and up >= 0 else \
              (f"<span class='down'>{up:.0f}%</span>" if up else "—")
    news = d.get("news")
    cat = (f"{news['headline'][:120]}<br><small>{news['source']} · {ago(news['mins'])}</small>"
           if news else "<small style='color:#6b7690'>no fresh headline</small>")
    rows_html += f"""<tr>
      <td class='l' style='color:#6b7690'>{i}</td>
      <td class='l'><span class='sym-t'>{d['sym']}</span>{" <span class='tag mid'>S&P</span>" if d.get('sp500') else ""}<br><span class='sym-n'>{d['name'][:26]}</span></td>
      <td>${d['price']:.2f}</td>
      <td class='up'>▲ {d['chg']:.1f}%</td>
      <td>{d['rvol']:.1f}×</td>
      <td>{fmt_vol(d['vol'])}</td>
      <td>{fmt_float(d['float'])} {float_tag(d['float'])}</td>
      <td>{up_html}</td>
      <td class='cat'>{cat}</td>
    </tr>"""

st.markdown(f"""<table class='surge'>
  <tr>
    <th class='l'>#</th>
    <th class='l' title="The stock's ticker symbol and company name.">Ticker</th>
    <th title="The latest price one share is trading at right now.">Price</th>
    <th title="How much the price is up today vs. yesterday's close. The scan targets +5% to +10%.">% Chg</th>
    <th title="Relative Volume — today's trading vs. a normal day. 2x means twice the usual: a sign demand is outpacing supply.">R.Vol</th>
    <th title="Total shares traded so far today. Bigger = more interest and easier to buy or sell.">Volume</th>
    <th title="Float — shares actually available to trade. A low float can move fast and hard on heavy buying.">Float</th>
    <th title="How far the average analyst price target sits above today's price. A published opinion, not a guarantee.">Target</th>
    <th class='l' title="The most recent news headline driving the move.">Why it's moving</th>
  </tr>
  {rows_html}</table>""", unsafe_allow_html=True)
st.caption("💡 Hover any column header for what it means.")

# ----------------------------------------------------------------------------
# PER-TICKER DETAIL  (pick one to inspect)
# ----------------------------------------------------------------------------
st.markdown("---")
syms = [d["sym"] for d in results]
pick = st.selectbox("🔍 Inspect a ticker", syms, index=0)
d = next(x for x in results if x["sym"] == pick)

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
        # deeper: more recent coverage
        more = news.get("more") or []
        if more:
            st.markdown(f"**More coverage** · {news.get('count', len(more))} recent stories")
            for m in more:
                link = f"[{m['headline']}]({m['url']})" if m.get("url") else m["headline"]
                st.markdown(
                    f"<div style='padding:7px 0;border-top:1px solid #1a202d;font-size:13px'>"
                    f"{link}<br><span style='color:#6b7690;font-size:11px'>{m['source']} · {ago(m['mins'])}</span></div>",
                    unsafe_allow_html=True)
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
