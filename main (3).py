import streamlit as st
import pandas as pd
import telebot
import time
import requests
from datetime import datetime
import numpy as np
import threading

# --- الإعدادات (ثابتة) ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'
APP_URL = "https://requirem-2w5fsgwlpzwxfa2zmmrdwk.streamlit.app/" 
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'GOLD']

# --- إدارة الحالة (Session State) ---
if 'ping_started' not in st.session_state:
    st.session_state.ping_started = True
if 'tracker' not in st.session_state:
    st.session_state.tracker = {symbol: 0 for symbol in SYMBOLS}
if 'last_heartbeat_hour' not in st.session_state:
    st.session_state.last_heartbeat_hour = -1

# وظيفة الزيارة الذاتية لمنع النوم
def keep_alive():
    while True:
        try:
            requests.get(APP_URL, timeout=10)
        except:
            pass
        time.sleep(120)

if 'thread_running' not in st.session_state:
    threading.Thread(target=keep_alive, daemon=True).start()
    st.session_state.thread_running = True

# --- دالة إرسال تنبيه النبض الساعي (الدقة بالثواني) ---
def send_hourly_heartbeat():
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    current_second = now.second
    
    # الشرط: الدقيقة 00 والثانية بين 0 و 40 (لتفادي تخطيها بسبب الـ sleep)
    if current_minute == 0 and 0 <= current_second <= 40:
        if st.session_state.last_heartbeat_hour != current_hour:
            try:
                exact_time = now.strftime('%H:00:00')
                msg = f"✅ **تنبيه حالة البوت (متصل)**\n━━━━━━━━━━━━━━\n🤖 النظام يعمل بكفاءة 24/7\n⏰ الوقت العالمي: {exact_time}\n📡 فحص السوق مستمر لـ {len(SYMBOLS)} أزواج."
                bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                st.session_state.last_heartbeat_hour = current_hour
            except:
                pass

# --- الاستراتيجية الصارمة ---
def real_opportunity_strategy(df):
    if len(df) < 100: return "NEUTRAL", 0
    close = df['close']
    volume = df['volumeto']
    
    ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
    
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean().iloc[-1]
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean().iloc[-1]
    rsi = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9, adjust=False).mean()
    
    avg_volume = volume.rolling(window=20).mean().iloc[-1]
    current_volume = volume.iloc[-1]
    last_price = close.iloc[-1]
    
    if (last_price > ema200 and current_volume > avg_volume and 50 < rsi < 65 and macd.iloc[-1] > signal_line.iloc[-1]):
        return "BUY", 99
    elif (last_price < ema200 and current_volume > avg_volume and 35 < rsi < 50 and macd.iloc[-1] < signal_line.iloc[-1]):
        return "SELL", 99
    return "NEUTRAL", 0

# --- المحرك الرئيسي ---
st.set_page_config(page_title="Professional Trading Bot")
st.title("🛡️ نموذج النسخ الاحترافي - متصل 24/7")

# فحص نبض الساعة قبل بدء تحليل السوق
send_hourly_heartbeat()

status_box = st.empty()

for sym in SYMBOLS:
    status_box.info(f"🔄 جاري تحليل {sym} وفق فلاتر السيولة والاتجاه...")
    s_name = sym.replace("USD", "").replace("GOLD", "XAU")
    url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s_name}&tsym=USD&limit=250&api_key={API_KEY}"
    
    try:
        res = requests.get(url, timeout=10).json()
        df = pd.DataFrame(res['Data']['Data'])
        price = df['close'].iloc[-1]
        decision, conf = real_opportunity_strategy(df)
        
        if decision != "NEUTRAL" and (time.time() - st.session_state.tracker[sym] > 600):
            atr = (df['high'] - df['low']).rolling(window=14).mean().iloc[-1]
            sl = round(price - (atr * 1.5), 5) if decision == "BUY" else round(price + (atr * 1.5), 5)
            tp = round(price + (atr * 2.5), 5) if decision == "BUY" else round(price - (atr * 2.5), 5)
            
            now_str = datetime.now().strftime("%H:%M:%S")
            emoji = "🟢 شراء" if decision == "BUY" else "🔴 بيع"
            
            msg = f"🎯 **إشارة مؤكدة: {sym}**\n💰 النوع: {emoji}\n📍 الدخول: {price}\n✅ الهدف: {tp}\n🛡️ الوقف: {sl}\n⏰ الوقت: {now_str}"
            
            bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
            st.session_state.tracker[sym] = time.time()
            st.success(f"🚀 تم إرسال إشارة {sym}")
    except:
        continue
    time.sleep(1)

# استراحة بسيطة ثم إعادة التشغيل التلقائي
time.sleep(30)
st.rerun()
