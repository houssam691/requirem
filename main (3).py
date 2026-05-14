import streamlit as st
import pandas as pd
import telebot
import time
import requests
from datetime import datetime, timedelta, timezone

# --- الإعدادات ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'

try:
    bot = telebot.TeleBot(TOKEN, threaded=False)
except Exception as e:
    bot = None

SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'GOLD']

# --- دالة الاستراتيجية ---
def real_opportunity_strategy(df):
    try:
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
    except:
        return "NEUTRAL", 0

# --- إدارة الحالة ---
if 'last_hour_sent' not in st.session_state:
    st.session_state.last_hour_sent = None
if 'tracker' not in st.session_state:
    st.session_state.tracker = {symbol: 0 for symbol in SYMBOLS}
if 'signal_count' not in st.session_state:
    st.session_state.signal_count = 0

# --- إعدادات الواجهة ---
st.set_page_config(page_title="Trading Bot", layout="wide")
st.title("⏳ نظام التداول الآلي المحترف")

# --- عرض عدادات الحالة ---
col1, col2, col3 = st.columns(3)
current_now = datetime.now(timezone.utc) + timedelta(hours=1)
col1.metric("الوقت الحالي", current_now.strftime("%H:%M:%S"))
col2.metric("حالة الاتصال", "🟢 متصل" if bot else "🔴 عطل")
col3.metric("إشارات اليوم", st.session_state.signal_count)

st.divider()

# --- منطق رسالة الساعة (بدون تكرار) ---
if current_now.minute == 0 and current_now.second <= 5: # نافذة 5 ثوانٍ عند رأس الساعة
    if st.session_state.last_hour_sent != current_now.hour:
        msg_heartbeat = f"✅ نظام التداول يعمل\n⏰ الوقت: {current_now.strftime('%H:%M:%S')}"
        if bot:
            try:
                bot.send_message(CHAT_ID, msg_heartbeat)
                st.session_state.last_hour_sent = current_now.hour
            except: pass

# --- تحليل العملات وإرسال الإشارات ---
for sym in SYMBOLS:
    s_name = sym.replace("USD", "").replace("GOLD", "XAU")
    url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s_name}&tsym=USD&limit=250&api_key={API_KEY}"
    
    try:
        res = requests.get(url, timeout=5).json()
        df = pd.DataFrame(res['Data']['Data'])
        if df.empty: continue
        
        decision, conf = real_opportunity_strategy(df)
        
        # إرسال الإشارة إذا كانت قوية ولم تُرسل في آخر 10 دقائق
        if decision != "NEUTRAL" and (time.time() - st.session_state.tracker[sym] > 600):
            emoji = '🟢' if decision == 'BUY' else '🔴'
            trend = 'صعود' if decision == 'BUY' else 'هبوط'
            entry_time = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%H:%M:%S")
            
            # الرسالة المطلوبة تماماً
            msg = f"""🎯 إشارة: {sym}
{emoji} الاتجاه: {trend}
⏳ مدة الصفقة: 01:00 دقيقة
⏰ وقت الدخول: {entry_time}
💪 الثقة: {conf}%"""

            if bot:
                bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                st.session_state.signal_count += 1
                st.session_state.tracker[sym] = time.time()
                st.success(f"🚀 تم إرسال إشارة {sym}")
                
    except:
        continue

# --- تحديث تلقائي ---
time.sleep(2)
st.rerun()
