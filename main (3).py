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

# تتبع الإشارات لمنع التكرار (5 دقائق لكل عملة)
if 'last_signal_tracker' not in st.session_state:
    st.session_state.last_signal_tracker = {symbol: 0 for symbol in SYMBOLS}

# --- دالة حساب المستويات ---
def calculate_levels(current_price, direction, df):
    recent_range = (df['high'] - df['low']).mean()
    if direction == "BUY":
        sl = current_price - (recent_range * 1.5)
        tp = current_price + (recent_range * 2.0)
    else:
        sl = current_price + (recent_range * 1.5)
        tp = current_price - (recent_range * 2.0)
    return round(sl, 5), round(tp, 5)

# --- الاستراتيجية (الفرصة الذهبية) ---
def advanced_predict(df):
    if len(df) < 50: return "NEUTRAL", 0
    close = df['close']
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + (gain / (loss + 1e-9)).iloc[-1]))
    
    last_close = close.iloc[-1]
    if last_close > ema20.iloc[-1] > ema50.iloc[-1] and 40 < rsi < 60:
        return "BUY", 95
    elif last_close < ema20.iloc[-1] < ema50.iloc[-1] and 40 < rsi < 60:
        return "SELL", 95
    return "NEUTRAL", 0

# --- واجهة Streamlit ---
st.set_page_config(page_title="Auto Scanner 24/7", page_icon="🤖")
st.title("🤖 محرك الفحص المستمر")
status_placeholder = st.empty()
log_placeholder = st.empty()

# --- حلقة الفحص الدائم ---
def start_scanning():
    while True:
        for symbol in SYMBOLS:
            status_placeholder.info(f"🔄 جاري فحص {symbol} الآن...")
            s = symbol.replace("USD", "").replace("GOLD", "XAU")
            url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s}&tsym=USD&limit=100&api_key={API_KEY}"
            
            try:
                res = requests.get(url, timeout=10).json()
                df = pd.DataFrame(res['Data']['Data'])
                current_price = df['close'].iloc[-1]
                direction, confidence = advanced_predict(df)
                
                current_ts = time.time()
                # التحقق من الشرط ومنع التكرار
                if direction != "NEUTRAL" and (current_ts - st.session_state.last_signal_time[symbol] > 300):
                    sl, tp = calculate_levels(current_price, direction, df)
                    
                    emoji = "🟢 شراء (BUY)" if direction == "BUY" else "🔴 بيع (SELL)"
                    signal_msg = f"🎯 **إشارة جديدة** 🎯\n━━━━━━━━━━━━━━\n💹 **الزوج:** #{symbol}\n🎰 **النوع:** {emoji}\n🔥 **قوة الإشارة:** {confidence}%\n\n📍 **الدخول:** {current_price}\n✅ **الهدف:** {tp}\n❌ **الوقف:** {sl}\n━━━━━━━━━━━━━━"
                    
                    bot.send_message(CHAT_ID, signal_msg, parse_mode="Markdown")
                    st.session_state.last_signal_time[symbol] = current_ts
                    log_placeholder.success(f"✅ أرسلت إشارة لـ {symbol} في {datetime.now().strftime('%H:%M:%S')}")
                
            except Exception as e:
                continue
            
            time.sleep(1) # راحة قصيرة بين كل عملة وأخرى لتجنب الضغط
        
        status_placeholder.success("✅ تم فحص الجميع. سأعيد الكرة بعد 30 ثانية...")
        time.sleep(30) # انتظار قبل دورة الفحص التالية

# بدء التشغيل
if __name__ == "__main__":
    if 'last_signal_time' not in st.session_state:
        st.session_state.last_signal_time = {symbol: 0 for symbol in SYMBOLS}
    start_scanning()
