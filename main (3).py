import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import telebot
import time
import requests
from datetime import datetime

# --- الإعدادات (بدون تغيير) ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = [
    'BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD',
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'GOLD'
]

if 'last_signal_time' not in st.session_state:
    st.session_state.last_signal_time = {symbol: 0 for symbol in SYMBOLS}

COOLDOWN_SECONDS = 600 # زيادة وقت التبريد لتناسب صفقات القنص

# --- دوال المؤشرات المطورة (Sniper Indicators) ---

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_mfi(df, period=14):
    """حساب مؤشر Money Flow Index لرقابة السيولة"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volumeto']
    positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(window=period).sum()
    negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(window=period).sum()
    mfi = 100 - (100 / (1 + (positive_flow / negative_flow)))
    return mfi

# --- واجهة المستخدم ---
st.set_page_config(page_title="Golden Sniper Monitor", layout="wide")
st.title("🎯 نظام القناص الذهبي - دقة عالية")
st.markdown("---")

selected_symbol = st.sidebar.selectbox("اختر الزوج للعرض البياني", SYMBOLS)
st.sidebar.success("✅ فلاتر القناص مفعلة (EMA 200 + MFI + RSI)")

metrics_col = st.columns(3)
chart_placeholder = st.empty()

def check_market_with_ui(symbol, is_viewed=False):
    try:
        now_ts = time.time()
        fsym = symbol[:-3] if any(x in symbol for x in ['USD', 'JPY', 'CAD']) else symbol[:3]
        tsym = symbol[-3:]
        if symbol == 'GOLD': fsym, tsym = 'XAU', 'USD'

        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit=250"
        response = requests.get(url, timeout=15).json()
        df = pd.DataFrame(response['Data']['Data'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # حساب فلاتر القناص
        df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()
        df['RSI'] = calculate_rsi(df['close'])
        df['MFI'] = calculate_mfi(df)
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # --- شروط القناص الذهبية ---
        # شراء: السعر فوق EMA200 + RSI تحت 25 + MFI تحت 20 + شمعة صاعدة
        is_long = (last['close'] > last['EMA200'] and 
                   last['RSI'] < 25 and 
                   last['MFI'] < 20 and 
                   last['close'] > last['open'])

        # بيع: السعر تحت EMA200 + RSI فوق 75 + MFI فوق 80 + شمعة هابطة
        is_short = (last['close'] < last['EMA200'] and 
                    last['RSI'] > 75 and 
                    last['MFI'] > 80 and 
                    last['close'] < last['open'])

        if now_ts - st.session_state.last_signal_time[symbol] >= COOLDOWN_SECONDS:
            if is_long:
                bot.send_message(CHAT_ID, f"🔥 قنص ذهبي (شراء): {symbol}\n📈 RSI: {round(last['RSI'], 2)}\n💧 MFI: {round(last['MFI'], 2)}")
                st.session_state.last_signal_time[symbol] = now_ts
            elif is_short:
                bot.send_message(CHAT_ID, f"🔥 قنص ذهبي (بيع): {symbol}\n📉 RSI: {round(last['RSI'], 2)}\n💧 MFI: {round(last['MFI'], 2)}")
                st.session_state.last_signal_time[symbol] = now_ts
        
        return df
    except: return None

# الحلقة الرئيسية
while True:
    for s in SYMBOLS:
        is_viewed = (s == selected_symbol)
        df_result = check_market_with_ui(s, is_viewed)
        
        if is_viewed and df_result is not None:
            last_row = df_result.iloc[-1]
            metrics_col[0].metric("السعر", f"${last_row['close']}")
            metrics_col[1].metric("MFI (سيولة)", round(last_row['MFI'], 2))
            metrics_col[2].metric("RSI (زخم)", round(last_row['RSI'], 2))

            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.5, 0.25, 0.25], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df_result['time'], open=df_result['open'], high=df_result['high'], low=df_result['low'], close=df_result['close'], name="Price"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_result['time'], y=df_result['EMA200'], line=dict(color='white', width=2), name="EMA 200"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_result['time'], y=df_result['MFI'], line=dict(color='cyan'), name="MFI"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_result['time'], y=df_result['RSI'], line=dict(color='magenta'), name="RSI"), row=3, col=1)
            
            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
            chart_placeholder.plotly_chart(fig, use_container_width=True)
            
        time.sleep(0.5)
