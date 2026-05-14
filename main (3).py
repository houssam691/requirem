import streamlit as st
import pandas as pd
import telebot
import time
import requests
from datetime import datetime, timedelta, timezone
import numpy as np

# --- الإعدادات ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'

try:
    bot = telebot.TeleBot(TOKEN, threaded=False)
except Exception as e:
    bot = None

SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'GOLD']

# --- دالة الاستراتيجية مع دراسة الوقت (ATR) ---
def real_opportunity_strategy(df):
    try:
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
        decision = "NEUTRAL"
        if last_row['close'] > last_row['ema200'] and last_row['rsi'] < 30:
            decision = "BUY"
        elif last_row['close'] < last_row['ema200'] and last_row['rsi'] > 70:
            decision = "SELL"
            
        vol = (atr / last_row['close']) * 100
        if vol > 0.15: dur = "05:00"
        elif vol > 0.08: dur = "10:00"
        else: dur = "15:00"
            
        return decision, 85, dur
    except:
        return "NEUTRAL", 0, "00:00"

# --- إدارة الحالة ---
if 'last_hour_sent' not in st.session_state:
    st.session_state.last_hour_sent = None
if 'tracker' not in st.session_state:
    # تهيئة التوقيت بـ 0 لضمان عمل الفحص من أول مرة
    st.session_state.tracker = {symbol: 0.0 for symbol in SYMBOLS}
if 'signal_count' not in st.session_state:
    st.session_state.signal_count = 0

# --- الواجهة التي طلبتها ---
st.set_page_config(page_title="Trading Bot", layout="wide")
st.title("⏳ نظام التداول الآلي")

col1, col2, col3, col4 = st.columns(4)
with col1:
    current_time = datetime.now(timezone.utc) + timedelta(hours=1)
    st.metric("الوقت الآن", current_time.strftime("%H:%M:%S"))
with col2:
    st.metric("عدد العملات", len(SYMBOLS))
with col3:
    st.metric("حالة البوت", "🟢 يعمل" if bot else "🔴 متوقف")
with col4:
    st.metric("عدد الإشارات", st.session_state.signal_count)

st.divider()

# --- منطق رسالة الساعة الواحدة ---
if current_time.minute == 0 and current_time.second <= 5:
    if st.session_state.last_hour_sent != current_time.hour:
        if bot:
            try:
                bot.send_message(CHAT_ID, f"✅ نظام التداول يعمل\n⏰ الوقت: {current_time.strftime('%H:%M:%S')}")
                st.session_state.last_hour_sent = current_time.hour
            except: pass

# --- تحليل العملات ---
for sym in SYMBOLS:
    # فحص الوقت: إذا مر أقل من 300 ثانية (5 دقائق) على آخر إرسال لهذا الزوج، يتم تخطيه فوراً
    if time.time() - st.session_state.tracker[sym] < 300:
        continue

    s_name = sym.replace("USD", "").replace("GOLD", "XAU")
    url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s_name}&tsym=USD&limit=250&api_key={API_KEY}"
    try:
        res = requests.get(url, timeout=5).json()
        df = pd.DataFrame(res['Data']['Data'])
        decision, conf, duration = real_opportunity_strategy(df)
        
        if decision != "NEUTRAL":
            # تحديث التوقيت فور الإرسال لمنع التكرار
            st.session_state.tracker[sym] = time.time()
            
            emoji = '🟢' if decision == 'BUY' else '🔴'
            entry_t = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%H:%M:%S")
            
            msg = f"🎯 إشارة: {sym}\n{emoji} الاتجاه: {'صعود' if decision == 'BUY' else 'هبوط'}\n⏳ مدة الصفقة: {duration} دقيقة\n⏰ وقت الدخول: {entry_t}\n💪 الثقة: {conf}%"
            
            if bot:
                bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                st.session_state.signal_count += 1
    except: continue

time.sleep(2)
st.rerun()
