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

# استخدام session_state لتخزين الساعة التي تم الإرسال فيها لمنع التكرار
if 'last_heartbeat_hour' not in st.session_state:
    st.session_state.last_heartbeat_hour = -1

@st.cache_resource
def get_global_tracker():
    return {symbol: 0 for symbol in SYMBOLS}

last_signal_tracker = get_global_tracker()

# --- دالة إرسال تنبيه النبض الساعي (بناءً على الثانية 00) ---
def send_hourly_heartbeat():
    now = datetime.now() # يعتمد على توقيت السيرفر العالمي
    current_hour = now.hour
    current_minute = now.minute
    current_second = now.second
    
    # الشرط: يجب أن نكون في الدقيقة 00 والثانية بين 0 و 30 
    # لضمان التقاطها حتى لو كان السكربت في حالة sleep للحظات
    if current_minute == 0 and 0 <= current_second <= 30:
        # التأكد أننا لم نرسل رسالة لهذه الساعة المحددة من قبل
        if st.session_state.last_heartbeat_hour != current_hour:
            try:
                # عرض الوقت بصيغة دقيقة جداً
                exact_time = now.strftime('%H:00:00')
                heartbeat_msg = f"""
✅ **تنبيه حالة البوت (وقت دقيق)**
━━━━━━━━━━━━━━
🤖 البوت يعمل بكفاءة حالياً.
⏰ التوقيت العالمي: {exact_time}
📡 مراقبة {len(SYMBOLS)} أزواج مستمرة.
━━━━━━━━━━━━━━
                """
                bot.send_message(CHAT_ID, heartbeat_msg, parse_mode="Markdown")
                
                # قفل الساعة الحالية
                st.session_state.last_heartbeat_hour = current_hour
                st.sidebar.success(f"تم إرسال نبض الساعة {current_hour} بنجاح.")
            except Exception as e:
                print(f"Heartbeat Error: {e}")

# --- دالة حساب مستويات التداول ---
def calculate_levels(current_price, direction, df):
    recent_range = (df['high'] - df['low']).mean()
    if direction == "BUY":
        sl = current_price - (recent_range * 1.5)
        tp = current_price + (recent_range * 2.0)
    else:
        sl = current_price + (recent_range * 1.5)
        tp = current_price - (recent_range * 2.0)
    return round(sl, 5), round(tp, 5)

# --- استراتيجية التنبؤ ---
def advanced_predict(df):
    if len(df) < 50: return "NEUTRAL", 0
    close = df['close']
    ema20 = close.ewm(span=20).mean().iloc[-1]
    rsi = (100 - (100 / (1 + (close.diff().where(close.diff() > 0, 0).mean() / (abs(close.diff().where(close.diff() < 0, 0)).mean() + 1e-9)))))
    
    if close.iloc[-1] > ema20 and rsi < 65:
        return "BUY", 85
    elif close.iloc[-1] < ema20 and rsi > 35:
        return "SELL", 85
    return "NEUTRAL", 0

# --- إعداد واجهة Streamlit ---
st.set_page_config(page_title="VIP Trading Signals", page_icon="💹")
st.sidebar.header("🕹️ التحكم والنبض")

# تشغيل فحص النبض الساعي بدقة الثانية
send_hourly_heartbeat()

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

        current_ts = time.time()
        if direction != "NEUTRAL" and (current_ts - last_signal_tracker[selected_symbol] > 300):
            sl, tp = calculate_levels(current_price, direction, df)
            emoji = "🟢 شراء (BUY)" if direction == "BUY" else "🔴 بيع (SELL)"
            signal_msg = f"🎯 **إشارة تداول جديدة** 🎯\n━━━━━━━━━━━━━━\n💹 **الزوج:** #{selected_symbol}\n🎰 **النوع:** {emoji}\n🔥 **قوة الإشارة:** {confidence}%\n\n📍 **نقطة الدخول:** {current_price}\n✅ **الهدف (TP):** {tp}\n❌ **وقف الخسارة (SL):** {sl}\n\n⏰ **الوقت:** {datetime.now().strftime('%H:%M')}\n━━━━━━━━━━━━━━\n⚡ *تنبيه: التداول ينطوي على مخاطر عالية*"
            
            bot.send_message(CHAT_ID, signal_msg, parse_mode="Markdown")
            last_signal_tracker[selected_symbol] = current_ts
            st.success(f"🚀 تم إرسال توصية {direction} بنجاح!")

    except Exception as e:
        st.error(f"حدث خطأ: {e}")

run_analysis()

# تحديث الواجهة كل 30 ثانية
time.sleep(30)
st.rerun()
