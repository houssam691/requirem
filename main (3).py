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

COOLDOWN_SECONDS = 300 

# ═══════════════════════════════════════════════════════════════════════
# الدوال الفنية
# ═══════════════════════════════════════════════════════════════════════

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def calculate_macd(series):
    exp1 = series.ewm(span=12, adjust=False).mean()
    exp2 = series.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal, macd - signal

def predict_next_5_minutes(df):
    if len(df) < 30:
        return "NEUTRAL", 0, 0, ["بيانات ناقصة"]
    
    last_price = df['close'].iloc[-1]
    rsi = calculate_rsi(df['close']).iloc[-1]
    macd, signal, hist = calculate_macd(df['close'])
    
    score = 0
    factors = []
    
    if rsi < 30: score += 2; factors.append("RSI تشبع بيع")
    if rsi > 70: score -= 2; factors.append("RSI تشبع شراء")
    if hist.iloc[-1] > 0: score += 2; factors.append("MACD إيجابي")
    if hist.iloc[-1] < 0: score -= 2; factors.append("MACD سلبي")
    
    direction = "BULLISH" if score > 1 else "BEARISH" if score < -1 else "NEUTRAL"
    confidence = min(100, abs(score) * 20)
    
    return direction, score, confidence, factors

# ═══════════════════════════════════════════════════════════════════════
# دالة جلب البيانات - النسخة الآمنة
# ═══════════════════════════════════════════════════════════════════════

def analyze_and_predict(symbol):
    # نضع قيم افتراضية (5 قيم) لنضمن عدم حدوث ValueError أبداً
    default_return = (None, "NEUTRAL", 0, 0, [])
    
    try:
        fsym = symbol[:-3] if any(x in symbol for x in ['USD', 'JPY', 'CAD']) else symbol[:3]
        tsym = symbol[-3:]
        if symbol == 'GOLD': fsym, tsym = 'XAU', 'USD'

        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit=100"
        response = requests.get(url, timeout=10).json()
        
        # التأكد من نجاح الاستجابة
        if response.get('Response') != 'Success':
            return default_return
        
        data = response.get('Data', {}).get('Data', [])
        if not data:
            return default_return
            
        df = pd.DataFrame(data)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        direction, score, confidence, factors = predict_next_5_minutes(df)
        return df, direction, score, confidence, factors
        
    except Exception:
        return default_return

# ═══════════════════════════════════════════════════════════════════════
# الواجهة الأساسية
# ═══════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="Safe Predictor", layout="wide")
st.title("🔮 نظام التنبؤ المستقر")

selected_symbol = st.sidebar.selectbox("اختر الزوج", SYMBOLS)
refresh_rate = st.sidebar.slider("تحديث كل (ثانية)", 5, 60, 20)

# استخدام الـ Unpacking الآمن
result = analyze_and_predict(selected_symbol)
# هنا نضمن دائماً أننا نستلم 5 قيم
df, direction, score, confidence, factors = result

if df is not None:
    # عرض النتائج
    st.metric("السعر الحالي", f"{df['close'].iloc[-1]}")
    if direction == "BULLISH": st.success(f"توقع صعود بقوة {confidence}%")
    elif direction == "BEARISH": st.error(f"توقع هبوط بقوة {confidence}%")
    else: st.info("الاتجاه محايد حالياً")
    
    # الرسم البياني
    fig = go.Figure(data=[go.Candlestick(x=df['time'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
    fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("⚠️ جاري محاولة الاتصال بمزود البيانات... يرجى الانتظار")

# إعادة التشغيل
time.sleep(refresh_rate)
st.rerun()
