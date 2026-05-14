import streamlit as st
import pandas as pd
import telebot
import time
import requests
from datetime import datetime, timedelta, timezone
import numpy as np
import threading

# --- وظيفة البقاء حياً (Self-Ping) ---
def keep_alive():
    while True:
        try:
            requests.get("http://localhost:8501") 
        except:
            pass
        time.sleep(300) # تنبيه كل 5 دقائق لضمان النشاط

threading.Thread(target=keep_alive, daemon=True).start()

# --- الإعدادات ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'

try:
    bot = telebot.TeleBot(TOKEN, threaded=False)
except:
    bot = None

SYMBOLS = [
    'BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'GOLD',
    'GBPAUD', 'EURAUD', 'USDCAD', 'CHFJPY', 'USDJPY', 
    'USDCHF', 'GBPCAD', 'EURCAD', 'GBPJPY', 'CADJPY', 
    'EURGBP', 'EURJPY', 'GBPCHF', 'GBPUSD', 'EURCHF', 
    'EURUSD', 'AUDCAD', 'AUDJPY', 'AUDCHF', 'AUDUSD'
]

# --- دالة الاستراتيجية المطورة ---
def real_opportunity_strategy(df, df_5m):
    try:
        # 1. تحليل الإطار الزمني الأكبر (5 دقائق)
        df_5m['ema200_5m'] = df_5m['close'].ewm(span=200, adjust=False).mean()
        trend_5m = "UP" if df_5m['close'].iloc[-1] > df_5m['ema200_5m'].iloc[-1] else "DOWN"

        # 2. حساب المؤشرات على الإطار الحالي (دقيقة)
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        df['tr'] = np.maximum(df['high'] - df['low'], 
                             np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                      abs(df['low'] - df['close'].shift(1))))
        atr = df['tr'].rolling(window=14).mean().iloc[-1]
        
        last_row = df.iloc[-1]
        prev_rsi = df['rsi'].iloc[-2]
        last_rsi = df['rsi'].iloc[-1]
        
        decision = "NEUTRAL"
        
        # شروط صارمة للدقة 90%
        if (trend_5m == "UP" and last_row['close'] > last_row['ema200'] and 
            prev_rsi < 30 and last_rsi >= 30 and last_row['close'] > last_row['open']):
            decision = "BUY"
        elif (trend_5m == "DOWN" and last_row['close'] < last_row['ema200'] and 
              prev_rsi > 70 and last_rsi <= 70 and last_row['close'] < last_row['open']):
            decision = "SELL"
            
        vol = (atr / last_row['close']) * 100
        dur = "05:00" if vol > 0.15 else "10:00" if vol > 0.08 else "15:00"
        return decision, 90, dur
    except:
        return "NEUTRAL", 0, "00:00"

# --- إدارة الحالة ---
if 'tracker' not in st.session_state:
    st.session_state.tracker = {symbol: 0.0 for symbol in SYMBOLS}
if 'signal_count' not in st.session_state:
    st.session_state.signal_count = 0

# --- الواجهة ---
st.set_page_config(page_title="High-Freq Bot", layout="wide")
st.title("⚡ نظام الفحص السريع (كل دقيقة)")

col1, col2, col3 = st.columns(3)
with col1:
    current_time = datetime.now(timezone.utc) + timedelta(hours=1)
    st.metric("الوقت (GMT+1)", current_time.strftime("%H:%M:%S"))
with col2:
    st.metric("حالة البوت", "🟢 فحص مستمر" if bot else "🔴 خطأ")
with col3:
    st.metric("إشارات الجلسة", st.session_state.signal_count)

st.divider()

# --- التحليل المستمر (تم تقليل الانتظار للفحص السريع) ---
for sym in SYMBOLS:
    # تقليل وقت الانتظار بين الإشارات لنفس العملة إلى دقيقة واحدة فقط
    if time.time() - st.session_state.tracker[sym] < 60: 
        continue

    if sym == 'GOLD': fsym, tsym = 'XAU', 'USD'
    elif len(sym) == 6: fsym, tsym = sym[:3], sym[3:]
    else: fsym, tsym = sym.replace("USD", ""), "USD"

    base_url = "https://min-api.cryptocompare.com/data/v2/histominute"
    try:
        r1 = requests.get(f"{base_url}?fsym={fsym}&tsym={tsym}&limit=250&api_key={API_KEY}", timeout=5).json()
        df_1m = pd.DataFrame(r1['Data']['Data'])
        
        r5 = requests.get(f"{base_url}?fsym={fsym}&tsym={tsym}&limit=250&aggregate=5&api_key={API_KEY}", timeout=5).json()
        df_5m = pd.DataFrame(r5['Data']['Data'])
        
        decision, conf, duration = real_opportunity_strategy(df_1m, df_5m)
        
        if decision != "NEUTRAL":
            st.session_state.tracker[sym] = time.time()
            emoji = '🟢' if decision == 'BUY' else '🔴'
            msg = f"🎯 إشارة: {sym}\n{emoji} الاتجاه: {'صعود' if decision == 'BUY' else 'هبوط'}\n⏳ المدة: {duration}\n💪 الثقة: {conf}%"
            if bot:
                bot.send_message(CHAT_ID, msg)
                st.session_state.signal_count += 1
    except: continue

# تحديث الصفحة كل 5 ثوانٍ لضمان استمرارية الحلقة البرمجية
time.sleep(5)
st.rerun()
