import streamlit as st
import pandas as pd
import telebot
import time
import requests
from datetime import datetime, timedelta # أضفنا timedelta لحساب وقت الانتهاء
import numpy as np
import threading

# --- الإعدادات (ثابتة) ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'
APP_URL = "https://requirem-2w5fsgwlpzwxfa2zmmrdwk.streamlit.app/" 
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'GOLD']

# إدارة الحالة
if 'tracker' not in st.session_state:
    st.session_state.tracker = {symbol: 0 for symbol in SYMBOLS}
if 'last_heartbeat_hour' not in st.session_state:
    st.session_state.last_heartbeat_hour = -1

# --- دالة حساب وقت انتهاء الصفقة ---
def calculate_expiry(entry_time, duration_minutes=15):
    # افتراضياً، الصفقة تنتهي بعد 15 دقيقة من وقت الدخول
    expiry_time = entry_time + timedelta(minutes=duration_minutes)
    return expiry_time.strftime("%H:%M:%S")

# --- المحرك الرئيسي المعدل للنظام الزمني ---
st.set_page_config(page_title="Time-Based Trading Bot")
st.title("⏳ نظام التداول الزمني الاحترافي")

status_box = st.empty()

for sym in SYMBOLS:
    status_box.info(f"🔄 جاري تحليل {sym} زمنياً...")
    s_name = sym.replace("USD", "").replace("GOLD", "XAU")
    # جلب بيانات الشموع (نستخدم فريم الدقيقة ليكون التحليل دقيقاً زمنياً)
    url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s_name}&tsym=USD&limit=100&api_key={API_KEY}"
    
    try:
        res = requests.get(url, timeout=10).json()
        df = pd.DataFrame(res['Data']['Data'])
        
        # استدعاء الاستراتيجية (نفس الفلاتر الفنية لكن المخرجات زمنية)
        from app import real_opportunity_strategy # استدعاء الاستراتيجية السابقة
        decision, conf = real_opportunity_strategy(df)
        
        if decision != "NEUTRAL" and (time.time() - st.session_state.tracker[sym] > 600):
            # حساب الأوقات
            entry_dt = datetime.now()
            entry_time_str = entry_dt.strftime("%H:%M:%S")
            expiry_time_str = calculate_expiry(entry_dt, duration_minutes=15) # يمكنك تغيير الـ 15 دقيقة
            
            emoji = "🟢 صعود (CALL)" if decision == "BUY" else "🔴 هبوط (PUT)"
            
            # الرسالة الجديدة التي طلبتها
            msg = f"""
🎯 **إشارة زمنية مؤكدة: {sym}**
━━━━━━━━━━━━━━
📈 **الاتجاه المتوقع:** {emoji}
⏰ **وقت الدخول الآن:** {entry_time_str}
⏳ **وقت انتهاء الصفقة:** {expiry_time_str}
💪 **قوة الاحتمال:** {conf}%
━━━━━━━━━━━━━━
⚠️ *ادخل الصفقة فور وصول الرسالة*
            """
            
            bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
            st.session_state.tracker[sym] = time.time()
            st.success(f"🚀 تم إرسال إشارة زمنية لـ {sym}")
            
    except Exception as e:
        continue
    time.sleep(1)

time.sleep(30)
st.rerun()
