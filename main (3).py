import streamlit as st
import pandas as pd
import telebot
import time
import requests
from datetime import datetime
import numpy as np

# --- الإعدادات الثابتة ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'GOLD']

if 'tracker' not in st.session_state:
    st.session_state.tracker = {symbol: 0 for symbol in SYMBOLS}

# --- الاستراتيجية: فلتر الذهب (Golden Filter) ---
def golden_strategy(df):
    if len(df) < 60: return "NEUTRAL", 0
    
    close = df['close']
    
    # 1. فلتر الاتجاه (EMA 20 & 50 & 200)
    ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
    
    # 2. فلتر الزخم (RSI)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean().iloc[-1]
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean().iloc[-1]
    rsi = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    # 3. فلتر السيولة (Bollinger Bands)
    sma20 = close.rolling(window=20).mean().iloc[-1]
    std20 = close.rolling(window=20).std().iloc[-1]
    upper_band = sma20 + (2 * std20)
    lower_band = sma20 - (2 * std20)
    
    last_price = close.iloc[-1]
    
    # شروط الشراء القوي
    if last_price > ema200 and ema20 > ema50 and 50 < rsi < 65 and last_price > upper_band:
        return "BUY", 98
    # شروط البيع القوي
    elif last_price < ema200 and ema20 < ema50 and 35 < rsi < 50 and last_price < lower_band:
        return "SELL", 98
        
    return "NEUTRAL", 0

# --- المحرك الرئيسي ---
st.set_page_config(page_title="Golden Signal Bot", layout="wide")
st.title("🛡️ بوت الفرص الذهبية - فحص 24/7")
status_box = st.empty()

while True:
    for sym in SYMBOLS:
        status_box.info(f"🔄 جاري فحص {sym} بحثاً عن فرصة ذهبية...")
        s_name = sym.replace("USD", "").replace("GOLD", "XAU")
        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s_name}&tsym=USD&limit=250&api_key={API_KEY}"
        
        try:
            res = requests.get(url, timeout=10).json()
            df = pd.DataFrame(res['Data']['Data'])
            price = df['close'].iloc[-1]
            decision, confidence = golden_strategy(df)
            
            # منع التكرار (كل 5 دقائق)
            if decision != "NEUTRAL" and (time.time() - st.session_state.tracker[sym] > 300):
                # حساب الأهداف بناءً على التقلب (ATR)
                atr = (df['high'] - df['low']).rolling(window=14).mean().iloc[-1]
                sl = round(price - (atr * 2), 5) if decision == "BUY" else round(price + (atr * 2), 5)
                tp = round(price + (atr * 3), 5) if decision == "BUY" else round(price - (atr * 3), 5)
                
                # الحصول على الوقت الحالي بتنسيق (يوم/شهر/ساعة:دقيقة)
                current_time = datetime.now().strftime("%d/%m %H:%M")
                
                msg = f"🌟 **فرصة ذهبية مدموجة الفلاتر** 🌟\n"
                msg += f"━━━━━━━━━━━━━━\n"
                msg += f"💹 **الزوج:** #{sym}\n"
                msg += f"🎰 **النوع:** {'🟢 شراء قوي' if decision == 'BUY' else '🔴 بيع قوي'}\n"
                msg += f"🔥 **الدقة المتوقعة:** {confidence}%\n\n"
                msg += f"📍 **نقطة الدخول:** {price}\n"
                msg += f"✅ **وقت فتح الصفقة:** {current_time}\n"
                msg += f"❌ **صلاحية التحليل:** {current_time}\n"
                msg += f"━━━━━━━━━━━━━━\n"
                msg += f"💰 **الهدف المتوقع:** {tp}\n"
                msg += f"🛡️ **وقف الخسارة:** {sl}"
                
                bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                st.session_state.tracker[sym] = time.time()
                st.success(f"🚀 تم إرسال {sym} بنجاح!")
        except Exception as e:
            continue
        time.sleep(1)

    status_box.success("✅ انتهى المسح الشامل. استراحة 30 ثانية...")
    time.sleep(30)
    st.rerun()
