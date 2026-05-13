import streamlit as st
import pandas as pd
import telebot
import time
import requests
from datetime import datetime
import numpy as np

# --- الإعدادات الأساسية ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'GOLD']

@st.cache_resource
def get_global_tracker():
    return {symbol: 0 for symbol in SYMBOLS}

last_signal_tracker = get_global_tracker()

# --- دالة حساب وقف الخسارة والهدف آلياً ---
def calculate_levels(current_price, direction, df):
    # حساب متوسط الحركة (ATR) لتحديد أهداف منطقية
    recent_range = (df['high'] - df['low']).mean()
    
    if direction == "BUY":
        sl = current_price - (recent_range * 1.5)
        tp = current_price + (recent_range * 2.0)
    else:
        sl = current_price + (recent_range * 1.5)
        tp = current_price - (recent_range * 2.0)
    return round(sl, 5), round(tp, 5)

# --- الاستراتيجية ---
def advanced_predict(df):
    if len(df) < 50: return "NEUTRAL", 0
    close = df['close']
    # حساب سريع للمؤشرات
    ema20 = close.ewm(span=20).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]
    rsi = (100 - (100 / (1 + (close.diff().where(close.diff() > 0, 0).mean() / (abs(close.diff().where(close.diff() < 0, 0)).mean() + 1e-9)))))
    
    if close.iloc[-1] > ema20 and rsi < 65:
        return "BUY", 85
    elif close.iloc[-1] < ema20 and rsi > 35:
        return "SELL", 85
    return "NEUTRAL", 0

# --- تشغيل البوت ---
st.set_page_config(page_title="VIP Trading Signals", page_icon="💹")
selected_symbol = st.sidebar.selectbox("اختر الزوج لمراقبته", SYMBOLS)

def run_analysis():
    s = selected_symbol.replace("USD", "").replace("GOLD", "XAU")
    url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s}&tsym=USD&limit=100&api_key={API_KEY}"
    
    try:
        res = requests.get(url, timeout=10).json()
        df = pd.DataFrame(res['Data']['Data'])
        current_price = df['close'].iloc[-1]
        direction, confidence = advanced_predict(df)
        
        st.metric(label=f"السعر الحالي لـ {selected_symbol}", value=current_price)

        # منع التكرار (كل 5 دقائق)
        current_ts = time.time()
        if direction != "NEUTRAL" and (current_ts - last_signal_tracker[selected_symbol] > 300):
            sl, tp = calculate_levels(current_price, direction, df)
            
            # تصميم الرسالة الجذابة
            emoji = "🟢 شراء (BUY)" if direction == "BUY" else "🔴 بيع (SELL)"
            signal_msg = f"""
🎯 **إشارة تداول جديدة** 🎯
━━━━━━━━━━━━━━
💹 **الزوج:** #{selected_symbol}
🎰 **النوع:** {emoji}
🔥 **قوة الإشارة:** {confidence}%

📍 **نقطة الدخول:** {current_price}
✅ **الهدف (TP):** {tp}
❌ **وقف الخسارة (SL):** {sl}

⏰ **الوقت:** {datetime.now().strftime('%H:%M')}
━━━━━━━━━━━━━━
⚡ *تنبيه: التداول ينطوي على مخاطر عالية*
            """
            
            bot.send_message(CHAT_ID, signal_msg, parse_mode="Markdown")
            last_signal_tracker[selected_symbol] = current_ts
            st.success(f"🚀 تم إرسال توصية {direction} بنجاح!")

    except Exception as e:
        st.error(f"حدث خطأ: {e}")

run_analysis()

# تحديث تلقائي للواجهة
time.sleep(30)
st.rerun()
