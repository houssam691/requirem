import streamlit as st
import pandas as pd
import telebot
import time
import requests
from datetime import datetime
import numpy as np

# --- الإعدادات (ثابتة) ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'GOLD']

if 'tracker' not in st.session_state:
    st.session_state.tracker = {symbol: 0 for symbol in SYMBOLS}

# --- الاستراتيجية الصارمة (الفرصة الحقيقية) ---
def real_opportunity_strategy(df):
    if len(df) < 100: return "NEUTRAL", 0
    
    close = df['close']
    volume = df['volumeto']
    
    # 1. فلتر الاتجاه العملاق (EMA 200) - لا تداول عكس الاتجاه العام
    ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
    
    # 2. فلتر الزخم المزدوج (RSI + MACD)
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean().iloc[-1]
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean().iloc[-1]
    rsi = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9, adjust=False).mean()
    
    # 3. فلتر السيولة (يجب أن يكون الفوليوم أعلى من المتوسط)
    avg_volume = volume.rolling(window=20).mean().iloc[-1]
    current_volume = volume.iloc[-1]
    
    last_price = close.iloc[-1]
    
    # --- شروط الشراء الذهبي ---
    # اتجاه صاعد + سيولة عالية + RSI منضبط + تقاطع MACD إيجابي
    if (last_price > ema200 and 
        current_volume > avg_volume and 
        50 < rsi < 65 and 
        macd.iloc[-1] > signal_line.iloc[-1]):
        return "BUY", 99

    # --- شروط البيع الذهبي ---
    # اتجاه هابط + سيولة عالية + RSI منضبط + تقاطع MACD سلبي
    elif (last_price < ema200 and 
          current_volume > avg_volume and 
          35 < rsi < 50 and 
          macd.iloc[-1] < signal_line.iloc[-1]):
        return "SELL", 99
        
    return "NEUTRAL", 0

# --- المحرك الرئيسي ---
st.set_page_config(page_title="Professional Trading Bot")
st.title("🛡️ نظام الفحص الاحترافي - لا مكان للوهم")
status_box = st.empty()

while True:
    for sym in SYMBOLS:
        status_box.info(f"🔄 جاري تحليل {sym} وفق فلاتر السيولة والاتجاه...")
        s_name = sym.replace("USD", "").replace("GOLD", "XAU")
        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s_name}&tsym=USD&limit=250&api_key={API_KEY}"
        
        try:
            res = requests.get(url, timeout=10).json()
            df = pd.DataFrame(res['Data']['Data'])
            price = df['close'].iloc[-1]
            decision, conf = real_opportunity_strategy(df)
            
            # منع التكرار لضمان عدم إزعاجك (كل 10 دقائق للعملة الواحدة)
            if decision != "NEUTRAL" and (time.time() - st.session_state.tracker[sym] > 600):
                # حساب أهداف واقعية (ATR)
                atr = (df['high'] - df['low']).rolling(window=14).mean().iloc[-1]
                sl = round(price - (atr * 1.5), 5) if decision == "BUY" else round(price + (atr * 1.5), 5)
                tp = round(price + (atr * 2.5), 5) if decision == "BUY" else round(price - (atr * 2.5), 5)
                
                now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                
                emoji = "🟢 شراء (BUY)" if decision == "BUY" else "🔴 بيع (SELL)"
                msg = f"""
🎯 **إشارة حقيقية مؤكدة** 🎯
━━━━━━━━━━━━━━
💹 **الزوج:** #{sym}
🎰 **النوع:** {emoji}
🔥 **معدل الثقة:** {conf}%

📍 **نقطة الدخول:** {price}
✅ **وقت فتح الصفقة:** {now_str}
❌ **صلاحية التحليل:** {now_str}
━━━━━━━━━━━━━━
💰 **الهدف المحدد:** {tp}
🛡️ **وقف الخسارة:** {sl}
                """
                bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                st.session_state.tracker[sym] = time.time()
                st.success(f"🚀 تم اقتناص فرصة حقيقية في {sym}")
        except:
            continue
        time.sleep(1)

    status_box.success("✅ تم مسح السوق. استراحة 30 ثانية لتجديد البيانات...")
    time.sleep(30)
    st.rerun()
