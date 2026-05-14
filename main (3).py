import streamlit as st
import pandas as pd
import telebot
import time
import requests
from datetime import datetime, timedelta, timezone
import numpy as np

# --- إعدادات التليجرام ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'

try:
    bot = telebot.TeleBot(TOKEN, threaded=False)
except:
    bot = None

# --- قائمة الأزواج ---
SYMBOLS = [
    'BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'GOLD',
    'GBPAUD', 'EURAUD', 'USDCAD', 'CHFJPY', 'USDJPY', 'USDCHF', 'GBPCAD',
    'EURCAD', 'GBPJPY', 'CADJPY', 'EURGBP', 'EURJPY', 'GBPCHF', 'GBPUSD',
    'EURCHF', 'EURUSD', 'AUDCAD', 'AUDJPY', 'AUDCHF', 'AUDUSD'
]

# --- الاستراتيجية ---
def get_signal(df_1m, df_5m):
    try:
        df_5m['ema200'] = df_5m['close'].ewm(span=200, adjust=False).mean()
        trend = "UP" if df_5m['close'].iloc[-1] > df_5m['ema200'].iloc[-1] else "DOWN"
        
        delta = df_1m['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        df_1m['tr'] = np.maximum(
            df_1m['high'] - df_1m['low'],
            np.maximum(abs(df_1m['high'] - df_1m['close'].shift(1)),
                      abs(df_1m['low'] - df_1m['close'].shift(1)))
        )
        atr = df_1m['tr'].rolling(window=14).mean().iloc[-1]
        volatility = (atr / df_1m['close'].iloc[-1]) * 100
        
        prev_rsi = rsi.iloc[-2]
        curr_rsi = rsi.iloc[-1]
        is_bullish = df_1m['close'].iloc[-1] > df_1m['open'].iloc[-1]
        
        signal = "NEUTRAL"
        confidence = 0
        
        if trend == "UP" and prev_rsi < 30 and curr_rsi >= 30 and is_bullish:
            signal = "BUY"
            confidence = 85
        elif trend == "DOWN" and prev_rsi > 70 and curr_rsi <= 70 and not is_bullish:
            signal = "SELL"
            confidence = 85
        
        if volatility > 0.2:
            duration = "05:00"
        elif volatility > 0.1:
            duration = "10:00"
        else:
            duration = "15:00"
        
        return signal, confidence, duration, df_1m['close'].iloc[-1]
        
    except:
        return "NEUTRAL", 0, "00:00", 0

# --- واجهة Streamlit ---
st.set_page_config(page_title="📡 نظام الإشارات", layout="wide", page_icon="📡")

st.title("📡 نظام الإشارات اللحظي")

# --- تهيئة session state ---
if 'last_signal_time' not in st.session_state:
    st.session_state.last_signal_time = {}
if 'signals_log' not in st.session_state:
    st.session_state.signals_log = []
if 'last_full_scan' not in st.session_state:
    st.session_state.last_full_scan = 0
if 'scan_counter' not in st.session_state:
    st.session_state.scan_counter = 0

# --- عرض الحالة ---
col1, col2, col3 = st.columns(3)
with col1:
    current_time = datetime.now(timezone.utc) + timedelta(hours=1)
    st.metric("🕐 الوقت", current_time.strftime("%H:%M:%S"))
with col2:
    st.metric("🔄 عدد الفحوصات", st.session_state.scan_counter)
with col3:
    st.metric("📊 إشارات اليوم", len(st.session_state.signals_log))

# --- مكان لعرض الإشارات الجديدة ---
signal_placeholder = st.empty()
status_placeholder = st.empty()

# --- الحلقة الرئيسية (فحص مستمر) ---
while True:
    try:
        scan_start = time.time()
        st.session_state.scan_counter += 1
        
        status_placeholder.info(f"🔄 فحص شامل رقم {st.session_state.scan_counter} - جاري فحص {len(SYMBOLS)} زوج...")
        
        new_signals_found = 0
        
        # فحص كل الأزواج
        for symbol in SYMBOLS:
            # منع التكرار: نفس الزوج كل 5 دقائق
            now = time.time()
            if symbol in st.session_state.last_signal_time:
                if now - st.session_state.last_signal_time[symbol] < 300:  # 5 دقائق
                    continue
            
            try:
                # جلب البيانات
                if symbol == 'GOLD':
                    fsym, tsym = 'XAU', 'USD'
                elif len(symbol) == 6:
                    fsym, tsym = symbol[:3], symbol[3:]
                else:
                    fsym, tsym = symbol.replace("USD", ""), "USD"
                
                url_1m = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit=100&api_key={API_KEY}"
                r1 = requests.get(url_1m, timeout=5).json()
                df_1m = pd.DataFrame(r1['Data']['Data'])
                
                url_5m = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit=100&aggregate=5&api_key={API_KEY}"
                r5 = requests.get(url_5m, timeout=5).json()
                df_5m = pd.DataFrame(r5['Data']['Data'])
                
                if df_1m.empty or df_5m.empty:
                    continue
                
                signal, confidence, duration, price = get_signal(df_1m, df_5m)
                
                if signal != "NEUTRAL":
                    st.session_state.last_signal_time[symbol] = time.time()
                    new_signals_found += 1
                    
                    # رسالة التليجرام
                    emoji = "🟢" if signal == "BUY" else "🔴"
                    direction_ar = "صعود" if signal == "BUY" else "هبوط"
                    entry_time = datetime.now()
                    
                    msg = f"""
🎯 **إشارة: {symbol}**

{emoji} **الاتجاه:** {direction_ar}
⏳ **مدة الصفقة:** {duration}
⏰ **وقت الدخول:** {entry_time.strftime('%H:%M:%S')}
💪 **الثقة:** {confidence}%
💰 **السعر:** {price:.4f}
"""
                    
                    if bot:
                        bot.send_message(CHAT_ID, msg)
                    
                    # تسجيل في السجل
                    st.session_state.signals_log.append({
                        'الوقت': entry_time.strftime('%H:%M:%S'),
                        'الزوج': symbol,
                        'الإشارة': direction_ar,
                        'المدة': duration,
                        'الثقة': confidence,
                        'السعر': price
                    })
                    
                    # عرض الإشارة الجديدة في الواجهة
                    with signal_placeholder.container():
                        st.success(f"🎯 **إشارة جديدة!** {symbol} - {direction_ar} - ثقة {confidence}%")
                        st.balloons()
                        
            except Exception as e:
                continue
        
        # تحديث حالة الفحص
        scan_duration = time.time() - scan_start
        status_placeholder.success(f"✅ اكتمل الفحص {st.session_state.scan_counter} - استغرق {scan_duration:.1f} ثانية - وجد {new_signals_found} إشارات جديدة")
        
        # عرض آخر 5 إشارات
        if st.session_state.signals_log:
            st.divider()
            st.subheader("📋 آخر الإشارات")
            df_log = pd.DataFrame(st.session_state.signals_log[-5:])
            st.dataframe(df_log, use_container_width=True)
        
        # انتظر 60 ثانية قبل الفحص التالي
        status_placeholder.info(f"⏳ انتظار 60 ثانية حتى الفحص التالي...")
        time.sleep(60)
        
    except Exception as e:
        status_placeholder.error(f"❌ خطأ: {e} - إعادة المحاولة بعد 30 ثانية")
        time.sleep(30)
