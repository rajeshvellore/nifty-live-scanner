import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import os
import numpy as np
from scipy.stats import norm
from streamlit_autorefresh import st_autorefresh

# 1. PAGE CONFIG
st.set_page_config(page_title="Nifty 50 Pro Agent", layout="wide")
refresh_count = st_autorefresh(interval=50000, key="niftyscan_refresh")

# --- 2. SMART CLOCK (IST) ---
if os.getenv("STREAMLIT_CLOUD_DASHBOARD") or os.getenv("HOSTNAME"):
    display_time = datetime.datetime.now() + datetime.timedelta(hours=5, minutes=30)
    env_label = "Cloud (IST)"
else:
    display_time = datetime.datetime.now()
    env_label = "Local (IST)"

# --- 3. MARKET DATA DASHBOARD ---
def get_market_summary():
    indexes = {"NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK", "INDIA VIX": "^INDIAVIX"}
    current_data = []
    for name, sym in indexes.items():
        try:
            h = yf.Ticker(sym).history(period="3d") 
            if not h.empty and len(h) >= 2:
                ltp, prev = h['Close'].iloc[-1], h['Close'].iloc[-2]
                pts, pct = ltp - prev, ((ltp - prev) / prev) * 100
                current_data.append({"name": name, "ltp": ltp, "pts": pts, "pct": pct})
        except:
            if 'last_market_data' in st.session_state:
                prev_entry = next((item for item in st.session_state.last_market_data if item["name"] == name), None)
                if prev_entry: current_data.append(prev_entry)
    if current_data: st.session_state.last_market_data = current_data
    return st.session_state.last_market_data

index_data = get_market_summary()
nifty_pct = next((item['pct'] for item in index_data if item['name'] == "NIFTY 50"), 0.01)
vix_val = next((item['ltp'] for item in index_data if item['name'] == "INDIA VIX"), 15.0)

st.title("🏹 Nifty 50 Pro Agent")
idx_cols = st.columns(3)
for i, item in enumerate(index_data):
    with idx_cols[i]:
        st.metric(label=item['name'], value=f"{item['ltp']:,.2f}", delta=f"{item['pts']:+,.2f} ({item['pct']:.2f}%)")

st.info(f"🕒 **{env_label} Clock:** {display_time.strftime('%H:%M:%S')}")
st.markdown("---")

# --- 4. SECTOR MAPPING ---
sector_map = {
    "ADANIENT": "Metals", "ADANIPORTS": "Services", "APOLLOHOSP": "Healthcare", "ASIANPAINT": "Consumer", "AXISBANK": "Banking",
    "BAJAJ-AUTO": "Auto", "BAJAJFINSV": "Fin Serv", "BAJFINANCE": "Fin Serv", "BEL": "Capital Goods", "BHARTIARTL": "Telecom",
    "BPCL": "Oil & Gas", "BRITANNIA": "Consumer", "CIPLA": "Healthcare", "COALINDIA": "Metals", "DRREDDY": "Healthcare",
    "EICHERMOT": "Auto", "GRASIM": "Materials", "HCLTECH": "IT", "HDFCBANK": "Banking", "HDFCLIFE": "Fin Serv",
    "HEROMOTOCO": "Auto", "HINDALCO": "Metals", "HINDUNILVR": "Consumer", "ICICIBANK": "Banking", "INDUSINDBK": "Banking",
    "INFY": "IT", "ITC": "Consumer", "JSWSTEEL": "Metals", "KOTAKBANK": "Banking", "LT": "Construction",
    "LTIM": "IT", "M&M": "Auto", "MARUTI": "Auto", "NESTLEIND": "Consumer", "NTPC": "Power",
    "ONGC": "Oil & Gas", "POWERGRID": "Power", "RELIANCE": "Energy", "SBILIFE": "Fin Serv", "SBIN": "Banking",
    "SHRIRAMFIN": "Fin Serv", "SUNPHARMA": "Healthcare", "TATACONSUM": "Consumer", "TATAMOTORS": "Auto", "TATASTEEL": "Metals",
    "TCS": "IT", "TECHM": "IT", "TITAN": "Consumer", "ULTRACEMCO": "Materials", "WIPRO": "IT"
}
tickers_list = sorted([s + ".NS" for s in sector_map.keys()])

# --- 5. CORE ANALYZER ---
def analyze_stock_live(ticker, days, direction, mkt_pct, only_reversals=False):
    try:
        df = yf.download(ticker, period="60d", interval="1d", progress=False, threads=False)
        if df.empty or len(df) < 25: return None
        closes, highs, lows, volumes = df['Close'].squeeze(), df['High'].squeeze(), df['Low'].squeeze(), df['Volume'].squeeze()
        
        delta = closes.diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi_val = (100 - (100 / (1 + (gain / loss)))).iloc[-1]
        tr = pd.concat([highs-lows, abs(highs-closes.shift(1)), abs(lows-closes.shift(1))], axis=1).max(axis=1)
        atr_val = tr.rolling(14).mean().iloc[-1]
        rvol = volumes.iloc[-1] / volumes.rolling(20).mean().iloc[-1]
        exhaust_ratio = (highs.iloc[-1] - lows.iloc[-1]) / (atr_val if atr_val > 0 else 1)
        
        recent = closes.tail(days + 1)
        match = all(recent.iloc[i] < recent.iloc[i-1] for i in range(1, len(recent))) if direction == "Falling" else all(recent.iloc[i] > recent.iloc[i-1] for i in range(1, len(recent)))

        if match:
            ltp = float(recent.iloc[-1])
            today_move = ((ltp - recent.iloc[-2]) / recent.iloc[-2]) * 100
            total_trend_move = ((ltp - recent.iloc[0]) / recent.iloc[0]) * 100
            rs_ratio = today_move / mkt_pct if mkt_pct != 0 else 1.0
            
            strike = round((ltp + (1.5*atr_val if direction == "Rising" else -1.5*atr_val))/5)*5
            z_score = abs(ltp - strike) / (atr_val if atr_val > 0 else 1)
            win_rate = norm.cdf(z_score) * 100
            safety_buf = (abs(ltp - strike) / ltp) * 100
            
            reasons = []
            if (direction == "Falling" and rsi_val < 35) or (direction == "Rising" and rsi_val > 65): reasons.append("RSI Extreme")
            if rvol > 1.4: reasons.append("Vol Spike")
            if exhaust_ratio > 1.1: reasons.append("ATR Exhausted")
            
            if only_reversals and not reasons: return None
            
            sym = ticker.replace(".NS", "")
            return {
                "Ticker": sym, "Sector": sector_map.get(sym, "NA"), "LTP": round(ltp, 2),
                "Suggestion": "🟢 BUY" if direction == "Falling" else "🔴 SELL",
                "Buyer Action": ("🔥 BUY " + ("CALL" if direction == "Falling" else "PUT")) if rvol > 1.5 else "Wait",
                "Seller Action": ("🛡️ SELL " + ("PUT" if direction == "Falling" else "CALL") + f" {strike}"),
                "Win Rate %": f"{round(win_rate)}%", "Safety Buffer": f"{round(safety_buf, 1)}%",
                "RSI": round(rsi_val, 1), "RVOL": round(rvol, 2), "RS Ratio": round(rs_ratio, 2),
                "Exhaustion %": f"{round(exhaust_ratio*100)}%", "Today %": round(today_move, 2),
                "Total %": round(total_trend_move, 2),
                "Reasoning": " + ".join(reasons) if reasons else "Trend Strength",
                "Chart": f"https://www.tradingview.com/chart/?symbol=NSE:{sym}"
            }
    except: return None

# --- 6. FIXED BUTTONS ---
st.sidebar.header("Scan Parameters")
look_val = st.sidebar.slider("Consecutive Days", 1, 10, 1) 
t_dir = st.sidebar.radio("Direction", ["Falling", "Rising"])
sel_tickers = st.sidebar.multiselect("Stocks", tickers_list, default=tickers_list)

if 'last_scan_time' not in st.session_state: st.session_state.last_scan_time = "Never"

c_btn1, c_btn2, c_time = st.columns([1, 1, 2])
with c_btn1:
    if st.button("🚀 Execute Global Scan", key="main_scan"):
        with st.spinner("Analyzing..."):
            res = [analyze_stock_live(t, look_val, t_dir, nifty_pct) for t in sel_tickers]
            st.session_state.scan_results = [r for r in res if r]
            st.session_state.last_scan_time = datetime.datetime.now().strftime("%H:%M:%S")
with c_btn2:
    if st.button("🎯 Reversals Only", key="rev_scan"):
        with st.spinner("Filtering..."):
            res = [analyze_stock_live(t, look_val, t_dir, nifty_pct, True) for t in sel_tickers]
            st.session_state.scan_results = [r for r in res if r]
            st.session_state.last_scan_time = datetime.datetime.now().strftime("%H:%M:%S")
# with c_time:
#     st.info(f"**Last Scanned At:** {st.session_state.last_scan_time}")

# --- 7. TABS LAYOUT ---
tab_morning, tab_trend, tab_buy, tab_sell, tab_ath_atl = st.tabs(["🔥 Morning Momentum", "🏹 Trend Scanner", "⚡ Option Buying", "🛡️ Option Selling", "🏔️ ATH / ATL"])

with tab_morning:
    st.subheader("☀️ Open = High / Open = Low Scanner")
    
    if st.button("🔎 Scan Morning Edge", key="morn_btn"):
        morn_res = []
        with st.spinner("Checking Intraday Openings..."):
            for t in sel_tickers:
                try:
                    m_df = yf.download(t, period="1d", interval="1m", progress=False)
                    if m_df.empty: continue
                    op, hi, lo, cp = m_df['Open'].iloc[0], m_df['High'].max(), m_df['Low'].min(), m_df['Close'].iloc[-1]
                    # Buffer of 0.05% for "Equal"
                    if abs(op - lo) / op < 0.0005: 
                        morn_res.append({"Ticker": t.replace(".NS",""), "Type": "🟢 Open = Low (Bullish)", "LTP": round(float(cp),2), "Day %": round(((cp-op)/op)*100,2)})
                    elif abs(op - hi) / op < 0.0005:
                        morn_res.append({"Ticker": t.replace(".NS",""), "Type": "🔴 Open = High (Bearish)", "LTP": round(float(cp),2), "Day %": round(((cp-op)/op)*100,2)})
                except: continue
        if morn_res: st.dataframe(pd.DataFrame(morn_res).sort_values(by="Day %", ascending=False))
        else: st.info("No stocks currently showing perfect Open=High or Open=Low matches.")

if 'scan_results' in st.session_state and st.session_state.scan_results:
    df = pd.DataFrame(st.session_state.scan_results)
    with tab_trend:
        st.dataframe(df[["Ticker", "Sector", "Suggestion", "LTP", "Today %", "Total %", "RSI", "Reasoning"]])
        l_cols = st.columns(5)
        for i, row in enumerate(st.session_state.scan_results):
            with l_cols[i % 5]: st.markdown(f"**[{row['Ticker']}]({row['Chart']})**")
    with tab_buy:
        st.dataframe(df[["Ticker", "Buyer Action", "RS Ratio", "RVOL", "RSI", "Today %"]].sort_values(by="RS Ratio", ascending=False))
    with tab_sell:
        st.dataframe(df[["Ticker", "Seller Action", "Win Rate %", "Safety Buffer", "Exhaustion %", "LTP"]].sort_values(by="Win Rate %", ascending=False))

with tab_ath_atl:
    st.subheader("🏔️ All-Time High / Low Tracker")
    if st.button("🔥 Scan Historical Records", key="ath_btn"):
        ath_res = []
        with st.spinner("Fetching Max History..."):
            for t in sel_tickers:
                try:
                    h_df = yf.download(t, period="max", interval="1d", progress=False)
                    hi, lo, cp = h_df['High'].max(), h_df['Low'].min(), h_df['Close'].iloc[-1]
                    if ((hi - cp)/hi)*100 < 1.2: ath_res.append({"Ticker": t.replace(".NS",""), "Type": "🏔️ ATH", "Price": round(float(hi),2), "Dist %": round(((hi-cp)/hi)*100,2)})
                    if ((cp - lo)/lo)*100 < 1.2: ath_res.append({"Ticker": t.replace(".NS",""), "Type": "🕳️ ATL", "Price": round(float(lo),2), "Dist %": round(((cp-lo)/lo)*100,2)})
                except: continue
        if ath_res: st.dataframe(pd.DataFrame(ath_res))
        else: st.info("No stocks near ATH or ATL levels.")

if 'scan_results' in st.session_state:
    st.markdown("---")
    csv_data = pd.DataFrame(st.session_state.scan_results).to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Full Report", csv_data, "nifty_pro_report.csv", "text/csv")