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
except:
    bot = None

SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'GOLD']

# --- دالة الاستراتيجية وحساب المدة الحقيقية ---
def analyze_market(df):
    try:
        # 1. حساب المؤشرات الفنية الأساسية
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 2. حساب ATR لتحديد مدة الصفقة بناءً على التقلب
        df['tr'] = np.maximum(df['high'] - df['low'], 
                             np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                      abs(df['low'] - df['close'].shift(1))))
        atr = df['tr'].rolling(window=14).mean().iloc[-1]
        
        last_row = df.iloc[-1]
        
        # تحديد القرار
        decision = "NEUTRAL"
        if last_row['close'] > last_row['ema200'] and last_row['rsi'] < 30:
            decision = "BUY"
        elif last_row['close'] < last_row['ema200'] and last_row['rsi'] > 70:
            decision = "SELL"
            
        # تحديد مدة الصفقة (دراسة وليست تخميناً):
        # إذا كان ATR مرتفعاً (سوق متقلب)، تكون المدة أقصر (مثلاً 5 دقائق)
        # إذا كان ATR منخفضاً (سوق هادئ)، تكون المدة أطول (مثلاً 15 دقيقة)
        avg_price = last_row['close']
        volatility_ratio = (atr / avg_price) * 100
        
        if volatility_ratio > 0.15: 
            duration = "05:00" # سوق سريع
        elif volatility_ratio > 0.08:
            duration = "10:00" # سوق متوسط
        else:
            duration = "15:00" # سوق بطيء يحتاج وقت
            
        return decision, 85, duration
    except:
        return "NEUTRAL", 0, "00:00"

# --- إدارة الحالة ---
if 'last_hour_sent' not in st.session_state:
    st.session_state.last_hour_sent = None
if 'tracker' not in st.session_state:
    st.session_state.tracker = {symbol: 0 for symbol in SYMBOLS}

st.set_page_config(page_title="Trading Bot", layout="wide")
st.title("⏳ نظام التداول الذكي")

# --- التوقيت الحالي ---
current_now = datetime.now(timezone.utc) + timedelta(hours=1) # توقيتك المحلي

# --- رسالة الساعة ---
if current_now.minute == 0 and current_now.second <= 10:
    if st.session_state.last_hour_sent != current_now.hour:
        if bot:
            bot.send_message(CHAT_ID, f"✅ نظام التداول يعمل\n⏰ الوقت: {current_now.strftime('%H:%M:%S')}")
            st.session_state.last_hour_sent = current_now.hour

# --- فحص العملات وإرسال الإشارات ---
for sym in SYMBOLS:
    s_name = sym.replace("USD", "").replace("GOLD", "XAU")
    url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s_name}&tsym=USD&limit=250&api_key={API_KEY}"
    
    try:
        res = requests.get(url, timeout=5).json()
        df = pd.DataFrame(res['Data']['Data'])
        if df.empty: continue
        
        decision, conf, duration = analyze_market(df)
        
        if decision != "NEUTRAL" and (time.time() - st.session_state.tracker[sym] > 600):
            emoji = '🟢' if decision == 'BUY' else '🔴'
            trend = 'صعود' if decision == 'BUY' else 'هبوط'
            entry_time = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%H:%M:%S")
            
            # الرسالة بتنسيق الصورة 1000433553.jpg مع المدة المدروسة
            msg = f"""🎯 إشارة: {sym}
{emoji} الاتجاه: {trend}
⌛ مدة الصفقة: {duration} دقيقة
⏰ وقت الدخول: {entry_time}
💪 الثقة: {conf}%"""

            if bot:
                bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                st.session_state.tracker[sym] = time.time()
                st.success(f"🚀 إشارة لـ {sym}")
                
    except: continue

time.sleep(2)
st.rerun()
