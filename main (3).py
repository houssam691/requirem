import streamlit as st
import pandas as pd
import telebot
import time
import requests
from datetime import datetime, timedelta
import numpy as np

# --- الإعدادات ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'GOLD']

# --- دالة الاستراتيجية المدمجة ---
def real_opportunity_strategy(df):
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    last_row = df.iloc[-1]
    if last_row['close'] > last_row['ema200'] and last_row['rsi'] < 30:
        return "BUY", 85
    elif last_row['close'] < last_row['ema200'] and last_row['rsi'] > 70:
        return "SELL", 85
    return "NEUTRAL", 0

# إدارة الحالة
if 'tracker' not in st.session_state:
    st.session_state.tracker = {symbol: 0 for symbol in SYMBOLS}
if 'last_heartbeat_hour' not in st.session_state:
    st.session_state.last_heartbeat_hour = -1

def calculate_expiry(entry_time, duration_minutes=15):
    expiry_time = entry_time + timedelta(minutes=duration_minutes)
    return expiry_time.strftime("%H:%M:%S")

st.set_page_config(page_title="Time-Based Trading Bot")
st.title("⏳ نظام التداول الزمني الاحترافي")

# --- رسالة نبض القلب (مرة واحدة كل ساعة) ---
current_hour = datetime.now().hour
if st.session_state.last_heartbeat_hour != current_hour:
    now_str = datetime.now().strftime("%Y-%m-%d %H:00:00")
    bot.send_message(CHAT_ID, f"✅ نظام التداول يعمل بنجاح\n⏰ الوقت الحالي: {now_str}")
    st.session_state.last_heartbeat_hour = current_hour

status_box = st.empty()

for sym in SYMBOLS:
    s_name = sym.replace("USD", "").replace("GOLD", "XAU")
    # الاقتراح 3: تقليل timeout لـ 5 ثوانٍ
    url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s_name}&tsym=USD&limit=250&api_key={API_KEY}"
    
    try:
        res = requests.get(url, timeout=5).json()
        df = pd.DataFrame(res['Data']['Data'])
        decision, conf = real_opportunity_strategy(df)
        
        if decision != "NEUTRAL" and (time.time() - st.session_state.tracker[sym] > 600):
            entry_dt = datetime.now()
            expiry_time_str = calculate_expiry(entry_dt, duration_minutes=15)
            emoji = "🟢 صعود (CALL)" if decision == "BUY" else "🔴 هبوط (PUT)"
            
            msg = f"""
🎯 **إشارة زمنية مؤكدة: {sym}**
━━━━━━━━━━━━━━
📈 **الاتجاه المتوقع:** {emoji}
⏰ **وقت الدخول الآن:** {entry_dt.strftime('%H:%M:%S')}
⏳ **وقت انتهاء الصفقة:** {expiry_time_str}
💪 **قوة الاحتمال:** {conf}%
━━━━━━━━━━━━━━
⚠️ *ادخل الصفقة فور وصول الرسالة*
            """
            bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
            st.session_state.tracker[sym] = time.time()
            st.success(f"🚀 تم إرسال إشارة لـ {sym}")
            
    except Exception as e:
        continue

# الاقتراح 2: تقليل وقت الانتظار الكلي لـ 10 ثوانٍ
status_box.write(f"✅ آخر تحديث: {datetime.now().strftime('%H:%M:%S')}")
time.sleep(10)
st.rerun()
