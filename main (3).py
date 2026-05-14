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
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'GOLD']

# --- دالة الاستراتيجية ---
def real_opportunity_strategy(df):
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    last_row = df.iloc[-1]
    if last_row['close'] > last_row['ema200'] and last_row['rsi'] < 30: return "BUY", 85
    elif last_row['close'] < last_row['ema200'] and last_row['rsi'] > 70: return "SELL", 85
    return "NEUTRAL", 0

# --- إدارة الحالة لضمان عدم التكرار ---
if 'last_heartbeat' not in st.session_state:
    st.session_state.last_heartbeat = None
if 'tracker' not in st.session_state:
    st.session_state.tracker = {symbol: 0 for symbol in SYMBOLS}

st.set_page_config(page_title="Trading Bot")
st.title("⏳ نظام التداول")

# --- منطق "رسالة واحدة كل ساعة" ---
current_time_utc = datetime.now(timezone.utc)
current_hour = current_time_utc.strftime("%Y-%m-%d %H") # صيغة الساعة فقط

if st.session_state.last_heartbeat != current_hour:
    # عرض الوقت بتوقيتك (UTC+1)
    display_time = (current_time_utc + timedelta(hours=1)).strftime("%d-%m-%Y %H:00:00")
    bot.send_message(CHAT_ID, f"✅ نظام التداول يعمل\n⏰ الساعة: {display_time}")
    st.session_state.last_heartbeat = current_hour

# --- تحليل العملات ---
for sym in SYMBOLS:
    s_name = sym.replace("USD", "").replace("GOLD", "XAU")
    url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s_name}&tsym=USD&limit=250&api_key={API_KEY}"
    try:
        res = requests.get(url, timeout=5).json()
        df = pd.DataFrame(res['Data']['Data'])
        decision, conf = real_opportunity_strategy(df)
        
        if decision != "NEUTRAL" and (time.time() - st.session_state.tracker[sym] > 600):
            msg = f"🎯 **إشارة: {sym}**\n📈 **الاتجاه:** {('🟢 صعود' if decision == 'BUY' else '🔴 هبوط')}"
            bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
            st.session_state.tracker[sym] = time.time()
    except: continue

time.sleep(15)
st.rerun()
