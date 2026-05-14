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

st.set_page_config(page_title="Time-Based Trading Bot")
st.title("⏳ نظام التداول الزمني الاحترافي")

# إدارة الحالة (Session State) لضمان عدم ضياع البيانات عند التحديث
if 'tracker' not in st.session_state:
    st.session_state.tracker = {symbol: 0 for symbol in SYMBOLS}

def calculate_expiry(entry_time, duration_minutes=15):
    expiry_time = entry_time + timedelta(minutes=duration_minutes)
    return expiry_time.strftime("%H:%M:%S")

status_box = st.empty()

# المحرك الرئيسي: بدلاً من حلقة for طويلة، نعالج الرموز بسرعة
for sym in SYMBOLS:
    s_name = sym.replace("USD", "").replace("GOLD", "XAU")
    url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s_name}&tsym=USD&limit=100&api_key={API_KEY}"
    
    try:
        # تقليل الـ timeout لسرعة الاستجابة
        res = requests.get(url, timeout=5).json()
        if 'Data' not in res: continue
        
        df = pd.DataFrame(res['Data']['Data'])
        
        # استدعاء الاستراتيجية (تأكد أن ملف app.py موجود في نفس المجلد)
        from app import real_opportunity_strategy 
        decision, conf = real_opportunity_strategy(df)
        
        # منع تكرار الإرسال (كل 10 دقائق لنفس الرمز)
        current_time = time.time()
        if decision != "NEUTRAL" and (current_time - st.session_state.tracker[sym] > 600):
            entry_dt = datetime.now()
            expiry_time_str = calculate_expiry(entry_dt, 15)
            emoji = "🟢 صعود (CALL)" if decision == "BUY" else "🔴 هبوط (PUT)"
            
            msg = f"🎯 **إشارة زمنية: {sym}**\n━━━━━━━━━━━━━━\n📈 **الاتجاه:** {emoji}\n⏰ **الدخول:** {entry_dt.strftime('%H:%M:%S')}\n⏳ **الانتهاء:** {expiry_time_str}\n💪 **القوة:** {conf}%\n━━━━━━━━━━━━━━"
            
            bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
            st.session_state.tracker[sym] = current_time
            st.success(f"🚀 تم إرسال إشارة {sym}")
            
    except Exception as e:
        st.error(f"Error with {sym}: {e}")
        continue

# الجزء الأهم: التوقف لفترة قصيرة ثم إعادة التشغيل
status_box.write(f"✅ آخر تحديث: {datetime.now().strftime('%H:%M:%S')}")
time.sleep(10) # انتظار 10 ثواني فقط لتخفيف الضغط
st.rerun()
