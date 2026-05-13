import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import telebot
import time
import requests
from datetime import datetime
import numpy as np

# --- الإعدادات ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = [
    'BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD',
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'GOLD'
]

if 'last_signal_time' not in st.session_state:
    st.session_state.last_signal_time = {symbol: 0 for symbol in SYMBOLS}

COOLDOWN_SECONDS = 300  # 5 دقائق

# ═══════════════════════════════════════════════════════════════════════
# دوال التحليل الفني
# ═══════════════════════════════════════════════════════════════════════

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_mfi(df, period=14):
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volumeto']
    positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(window=period).sum()
    negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(window=period).sum()
    return 100 - (100 / (1 + (positive_flow / negative_flow)))

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_momentum(series, period=3):
    return series - series.shift(period)

def calculate_atr(df, period=14):
    df['tr1'] = df['high'] - df['low']
    df['tr2'] = abs(df['high'] - df['close'].shift())
    df['tr3'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
    return df['tr'].rolling(window=period).mean()

# ═══════════════════════════════════════════════════════════════════════
# محرك التنبؤ
# ═══════════════════════════════════════════════════════════════════════

def predict_next_5_minutes(df):
    if len(df) < 50:
        return "NEUTRAL", 0, 0, ["⚠️ بيانات غير كافية"]
    
    df = df.copy()
    df['RSI'] = calculate_rsi(df['close'], 14)
    df['MFI'] = calculate_mfi(df, 14)
    df['MACD'], df['MACD_Signal'], df['MACD_Histogram'] = calculate_macd(df['close'])
    df['EMA20'] = calculate_ema(df['close'], 20)
    df['EMA50'] = calculate_ema(df['close'], 50)
    df['Momentum'] = calculate_momentum(df['close'], 3)
    df['ATR'] = calculate_atr(df, 14)
    
    last = df.iloc[-1]
    prediction_score = 0
    factors = []
    
    # منطق الاتجاه
    if last['close'] > last['EMA20'] > last['EMA50']:
        prediction_score += 3
        factors.append("✅ اتجاه صاعد قوي (EMA)")
    elif last['close'] < last['EMA20'] < last['EMA50']:
        prediction_score -= 3
        factors.append("❌ اتجاه هابط قوي (EMA)")
        
    # منطق RSI
    if last['RSI'] < 30:
        prediction_score += 2
        factors.append("🟢 تشبع بيعي (RSI)")
    elif last['RSI'] > 70:
        prediction_score -= 2
        factors.append("🔴 تشبع شرائي (RSI)")
        
    # منطق MACD
    if last['MACD_Histogram'] > 0:
        prediction_score += 2
        factors.append("📈 زخم MACD إيجابي")
    else:
        prediction_score -= 2
        factors.append("📉 زخم MACD سلبي")

    confidence = min(100, (abs(prediction_score) / 10) * 100)
    direction = "BULLISH" if prediction_score > 2 else "BEARISH" if prediction_score < -2 else "NEUTRAL"
    
    return direction, prediction_score, confidence, factors

# ═══════════════════════════════════════════════════════════════════════
# جلب البيانات (التعديل الأساسي هنا)
# ═══════════════════════════════════════════════════════════════════════

def analyze_and_predict(symbol):
    try:
        fsym = symbol[:-3] if any(x in symbol for x in ['USD', 'JPY', 'CAD']) else symbol[:3]
        tsym = symbol[-3:]
        if symbol == 'GOLD': fsym, tsym = 'XAU', 'USD'

        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit=300"
        response = requests.get(url, timeout=15).json()
        
        if response.get('Response') != 'Success':
            return None, None, None, None, None # تم توحيد عدد القيم (5)
        
        df = pd.DataFrame(response['Data']['Data'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        direction, score, confidence, factors = predict_next_5_minutes(df)
        return df, direction, score, confidence, factors
    except Exception as e:
        return None, None, None, None, None # تم توحيد عدد القيم (5)

# ═══════════════════════════════════════════════════════════════════════
# الواجهة والعرض
# ═══════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="5 Minute Predictor", layout="wide")
st.title("🔮 نظام التنبؤ - الـ 5 دقائق القادمة")

selected_symbol = st.sidebar.selectbox("اختر الزوج", SYMBOLS)
refresh_rate = st.sidebar.slider("سرعة التحديث (ثانية)", 5, 30, 15)

placeholder_main = st.empty()

def update_display():
    # استلام النتائج ككتلة واحدة للتأكد من العدد
    result = analyze_and_predict(selected_symbol)
    df, direction, score, confidence, factors = result
    
    if df is None:
        st.error("⚠️ فشل الاتصال بالخادم. سيتم المحاولة مرة أخرى...")
        return

    with placeholder_main.container():
        # عرض التنبؤ
        if direction == "BULLISH":
            st.success(f"### 📈 الحركة القادمة المتوقعة: صاعدة ({confidence:.1f}%)")
        elif direction == "BEARISH":
            st.error(f"### 📉 الحركة القادمة المتوقعة: هابطة ({confidence:.1f}%)")
        else:
            st.warning("### 〰️ الحركة الحالية: محايدة")

        # المقاييس
        c1, c2, c3 = st.columns(3)
        c1.metric("السعر الحالي", f"${df.iloc[-1]['close']:.4f}")
        c2.metric("قوة الإشارة", f"{score:.1f}/10")
        c3.metric("الثقة", f"{confidence:.1f}%")

        # العوامل والرسوم (تبسيطاً للعرض)
        st.write("🔍 **العوامل المؤثرة:** ", ", ".join(factors))
        
        # التنبيه لتلغرام
        now = time.time()
        if direction != "NEUTRAL" and (now - st.session_state.last_signal_time[selected_symbol] >= COOLDOWN_SECONDS):
            try:
                msg = f"🔮 تنبيه {selected_symbol}\nالاتجاه: {direction}\nالثقة: {confidence:.1f}%\nالسعر: {df.iloc[-1]['close']}"
                bot.send_message(CHAT_ID, msg)
                st.session_state.last_signal_time[selected_symbol] = now
            except: pass

update_display()

# إعادة التشغيل التلقائي
time.sleep(refresh_rate)
st.rerun()
