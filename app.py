import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

st.set_page_config(page_title="Nifty 50 Live Trend", layout="wide")

st.title("🏹 Nifty 50 Live Trend Scanner")
st.markdown("Scanning for strict consecutive price action including today's live market.")

nifty_50 = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BAJFINANCE.NS", "BEL.NS", "BHARTIARTL.NS",
    "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "INDUSINDBK.NS",
    "INFY.NS", "ITC.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "LTIM.NS", "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS",
    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS",
    "SHRIRAMFIN.NS", "SUNPHARMA.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS",
    "TCS.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS"
]

if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None

# --- SIDEBAR ---
st.sidebar.header("Live Parameters")
lookback = st.sidebar.slider("Consecutive Days (Including Today)", 1, 10, 3) 
trend = st.sidebar.radio("Direction", ["Falling", "Rising"])
min_change = st.sidebar.slider("Min % Change Today", 0.0, 5.0, 0.2)
tickers = st.sidebar.multiselect("Stocks", nifty_50, default=nifty_50)

def calculate_rsi_manual(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock_live(ticker, days, direction):
    try:
        # Pull 60 days to ensure RSI is accurate
        df = yf.download(ticker, period="60d", interval="1d", progress=False)
        if df.empty or len(df) < 20: return None

        # Clean data (handles MultiIndex if present)
        closes = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        volumes = df['Volume'].iloc[:, 0] if isinstance(df['Volume'], pd.DataFrame) else df['Volume']
        
        # Get live data for today
        current_rsi = calculate_rsi_manual(closes).iloc[-1]
        
        # We need (days + 1) prices to check (days) number of moves
        # e.g., for 1 day lookback, we need Today and Yesterday to compare.
        recent = closes.tail(days + 1)
        
        # STRICT CONSECUTIVE LOGIC
        if direction == "Falling":
            # Checks if every day is lower than the previous day, ending with Today
            match = all(recent.iloc[i] < recent.iloc[i-1] for i in range(1, len(recent)))
        else:
            # Checks if every day is higher than the previous day, ending with Today
            match = all(recent.iloc[i] > recent.iloc[i-1] for i in range(1, len(recent)))

        if match:
            # Calculate today's specific move % (Live vs Yesterday Close)
            today_move = ((recent.iloc[-1] - recent.iloc[-2]) / recent.iloc[-2]) * 100
            
            if abs(today_move) >= min_change:
                # Reversal Chance Logic (RSI + Volume)
                score = 0
                if direction == "Falling" and current_rsi < 30: score += 1
                elif direction == "Rising" and current_rsi > 70: score += 1
                if volumes.iloc[-1] > volumes.mean(): score += 1
                
                return {
                    "Ticker": ticker.replace(".NS", ""),
                    "LTP": round(float(recent.iloc[-1]), 2),
                    "Today %": round(float(today_move), 2),
                    "RSI": round(float(current_rsi), 1),
                    "Reversal %": f"{round((score/2)*100)}%",
                    "Vol Status": "High" if volumes.iloc[-1] > volumes.mean() else "Normal"
                }
    except: return None
    return None

# --- RUN SCAN ---
if st.button(f"Scan Nifty 50 Live"):
    results = []
    progress = st.progress(0)
    for i, t in enumerate(tickers):
        res = analyze_stock_live(t, lookback, trend)
        if res: results.append(res)
        progress.progress((i + 1) / len(tickers))
    st.session_state.scan_results = results

# --- DISPLAY RESULTS ---
if st.session_state.scan_results:
    res_df = pd.DataFrame(st.session_state.scan_results)
    now = datetime.datetime.now().strftime("%H:%M:%S")
    st.success(f"Matches found at {now}")
    
    # st.dataframe allows interactive sorting by clicking headers
    st.dataframe(res_df)
    
    @st.cache
    def convert_df(df):
        return df.to_csv(index=False).encode('utf-8')
    
    csv_data = convert_df(res_df)
    st.download_button("📥 Download Results", csv_data, f"nifty_live_{trend}.csv", "text/csv")