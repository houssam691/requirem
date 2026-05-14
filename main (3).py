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

SYMBOLS = [
    'BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'GOLD',
    'GBPAUD', 'EURAUD', 'USDCAD', 'CHFJPY', 'USDJPY', 
    'USDCHF', 'GBPCAD', 'EURCAD', 'GBPJPY', 'CADJPY', 
    'EURGBP', 'EURJPY', 'GBPCHF', 'GBPUSD', 'EURCHF', 
    'EURUSD', 'AUDCAD', 'AUDJPY', 'AUDCHF', 'AUDUSD'
]

# --- دالة الاستراتيجية المطورة (MTF + Price Action) ---
def real_opportunity_strategy(df, df_5m):
    try:
        # 1. تحليل الإطار الزمني الأكبر (5 دقائق) - Multi-Timeframe
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
        
        # 3. بيانات الشموع الحالية (Price Action)
        last_row = df.iloc[-1]
        prev_rsi = df['rsi'].iloc[-2]
        last_rsi = df['rsi'].iloc[-1]
        
        decision = "NEUTRAL"
        
        # شرط الشراء المحترف:
        # اتجاه 5 دقائق صاعد + السعر فوق EMA200 + تقاطع RSI صعوداً + الشمعة الحالية خضراء
        if (trend_5m == "UP" and 
            last_row['close'] > last_row['ema200'] and 
            prev_rsi < 30 and last_rsi >= 30 and 
            last_row['close'] > last_row['open']):
            decision = "BUY"
            
        # شرط البيع المحترف:
        # اتجاه 5 دقائق هابط + السعر تحت EMA200 + تقاطع RSI هبوطاً + الشمعة الحالية حمراء
        elif (trend_5m == "DOWN" and 
              last_row['close'] < last_row['ema200'] and 
              prev_rsi > 70 and last_rsi <= 70 and 
              last_row['close'] < last_row['open']):
            decision = "SELL"
            
        vol = (atr / last_row['close']) * 100
        if vol > 0.15: dur = "05:00"
        elif vol > 0.08: dur = "10:00"
        else: dur = "15:00"
            
        return decision, 90, dur # رفع نسبة الثقة في الرسالة إلى 90%
    except:
        return "NEUTRAL", 0, "00:00"

# --- إدارة الحالة ---
if 'last_hour_sent' not in st.session_state:
    st.session_state.last_hour_sent = None
if 'tracker' not in st.session_state:
    st.session_state.tracker = {symbol: 0.0 for symbol in SYMBOLS}
if 'signal_count' not in st.session_state:
    st.session_state.signal_count = 0

# --- الواجهة الأصلية ---
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

# --- رسالة الساعة الواحدة ---
if current_time.minute == 0 and current_time.second <= 5:
    if st.session_state.last_hour_sent != current_time.hour:
        if bot:
            try:
                bot.send_message(CHAT_ID, f"✅ نظام التداول يعمل\n⏰ الوقت: {current_time.strftime('%H:%M:%S')}")
                st.session_state.last_hour_sent = current_time.hour
            except: pass

# --- تحليل العملات ---
for sym in SYMBOLS:
    if time.time() - st.session_state.tracker[sym] < 300:
        continue

    if sym == 'GOLD':
        fsym, tsym = 'XAU', 'USD'
    elif len(sym) == 6:
        fsym, tsym = sym[:3], sym[3:]
    else:
        fsym, tsym = sym.replace("USD", ""), "USD"

    # طلب بيانات فريم الدقيقة وفريم 5 دقائق
    base_url = "https://min-api.cryptocompare.com/data/v2/histominute"
    try:
        # فريم دقيقة واحدة
        res_1m = requests.get(f"{base_url}?fsym={fsym}&tsym={tsym}&limit=250&api_key={API_KEY}", timeout=5).json()
        df_1m = pd.DataFrame(res_1m['Data']['Data'])
        
        # فريم 5 دقائق
        res_5m = requests.get(f"{base_url}?fsym={fsym}&tsym={tsym}&limit=250&aggregate=5&api_key={API_KEY}", timeout=5).json()
        df_5m = pd.DataFrame(res_5m['Data']['Data'])
        
        decision, conf, duration = real_opportunity_strategy(df_1m, df_5m)
        
        if decision != "NEUTRAL":
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
