import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import telebot
import time
import requests
from datetime import datetime

# --- الإعدادات الأصلية ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = [
    'BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD',
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'GOLD'
]

# ذاكرة الجلسة لمنع تكرار نفس التنبيه في وقت قصير
if 'last_signal_time' not in st.session_state:
    st.session_state.last_signal_time = {symbol: 0 for symbol in SYMBOLS}

COOLDOWN_SECONDS = 300 

def calculate_rsi(series, period=14):
    try:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    except: return pd.Series([50] * len(series))

# --- إعدادات الواجهة ---
st.set_page_config(page_title="Silent Pro Monitor", layout="wide")
st.title("🛡️ نظام المراقبة الصامت")
st.markdown("---")

selected_symbol = st.sidebar.selectbox("اختر الزوج للعرض البياني", SYMBOLS)
st.sidebar.success("✅ البوت يرسل الصفقات فقط الآن.")

metrics_col = st.columns(3)
chart_placeholder = st.empty()

def check_market_with_ui(symbol, is_viewed=False):
    try:
        now_ts = time.time()
        fsym = symbol[:-3] if any(x in symbol for x in ['USD', 'JPY', 'CAD']) else symbol[:3]
        tsym = symbol[-3:]
        if symbol == 'GOLD': fsym, tsym = 'XAU', 'USD'

        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit=50"
        response = requests.get(url, timeout=15).json()
        df = pd.DataFrame(response['Data']['Data'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df['EMA'] = df['close'].ewm(span=50, adjust=False).mean()
        df['RSI'] = calculate_rsi(df['close'])
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # إرسال الصفقات فقط (تم إلغاء كل الرسائل الأخرى)
        if now_ts - st.session_state.last_signal_time[symbol] >= COOLDOWN_SECONDS:
            if last['close'] > last['EMA'] and prev['RSI'] < 30 and last['RSI'] >= 30:
                bot.send_message(CHAT_ID, f"🎯 فرصة صعود: {symbol}\n📈 RSI: {round(last['RSI'], 2)}")
                st.session_state.last_signal_time[symbol] = now_ts
            elif last['close'] < last['EMA'] and prev['RSI'] > 70 and last['RSI'] <= 70:
                bot.send_message(CHAT_ID, f"🎯 فرصة هبوط: {symbol}\n📉 RSI: {round(last['RSI'], 2)}")
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
            metrics_col[1].metric("RSI", round(last_row['RSI'], 2))
            metrics_col[2].metric("الاتجاه", "صاعد" if last_row['close'] > last_row['EMA'] else "هابط")

            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df_result['time'], open=df_result['open'], high=df_result['high'], low=df_result['low'], close=df_result['close'], name="Screener"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_result['time'], y=df_result['EMA'], line=dict(color='orange'), name="EMA 50"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_result['time'], y=df_result['RSI'], line=dict(color='magenta'), name="RSI"), row=2, col=1)
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
            chart_placeholder.plotly_chart(fig, use_container_width=True)
            
        time.sleep(0.5)
