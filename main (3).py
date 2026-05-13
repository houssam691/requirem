import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import telebot
import time
import requests
from datetime import datetime
import numpy as np

# --- الإعدادات الثابتة ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7' # تم الدمج
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = [
    'BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD',
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'GOLD'
]

# حل مشكلة الـ Cooldown مع Cron-job (استخدام التخزين المؤقت)
if 'last_signal_time' not in st.session_state:
    st.session_state.last_signal_time = {symbol: 0 for symbol in SYMBOLS}

COOLDOWN_SECONDS = 300 

# --- الدوال الحسابية (تم إضافة حماية ضد القسمة على صفر) ---

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9) # حماية
    return 100 - (100 / (1 + rs))

def calculate_mfi(df, period=14):
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volumeto']
    positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(window=period).sum()
    negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(window=period).sum()
    mfi = 100 - (100 / (1 + (positive_flow / (negative_flow + 1e-9)))) # حماية
    return mfi

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_atr(df, period=14):
    df['tr'] = np.maximum(df['high'] - df['low'], 
                          np.maximum(abs(df['high'] - df['close'].shift()), 
                                     abs(df['low'] - df['close'].shift())))
    return df['tr'].rolling(window=period).mean()

# --- محرك التنبؤ ---
def predict_next_5_minutes(df):
    if len(df) < 20: return None, 0, 0, []
    
    df['RSI'] = calculate_rsi(df['close'])
    df['MFI'] = calculate_mfi(df)
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calculate_macd(df['close'])
    df['EMA20'] = calculate_ema(df['close'], 20)
    df['EMA50'] = calculate_ema(df['close'], 50)
    df['ATR'] = calculate_atr(df)
    
    last = df.iloc[-1]
    prediction_score = 0
    factors = []
    
    # منطق التنبؤ (كما هو في كودك مع تحسينات بسيطة)
    if last['close'] > last['EMA20'] > last['EMA50']: prediction_score += 3
    if last['RSI'] < 30: prediction_score += 2
    elif last['RSI'] > 70: prediction_score -= 2
    if last['MACD'] > last['MACD_Signal']: prediction_score += 2
    
    confidence = min(100, (abs(prediction_score) / 10) * 100)
    direction = "BULLISH" if prediction_score > 2 else "BEARISH" if prediction_score < -2 else "NEUTRAL"
    
    return direction, prediction_score, confidence, [f"RSI: {last['RSI']:.1f}", f"Score: {prediction_score}"]

# --- الواجهة ---
st.set_page_config(page_title="5 Minute Predictor", layout="wide")
selected_symbol = st.sidebar.selectbox("اختر الزوج", SYMBOLS)
refresh_rate = st.sidebar.slider("تحديث (ثانية)", 5, 60, 20)

def analyze_and_predict(symbol):
    try:
        s = symbol.replace("USD", "").replace("GOLD", "XAU")
        # تم إضافة API_KEY للرابط
        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s}&tsym=USD&limit=150&api_key={API_KEY}"
        res = requests.get(url, timeout=10).json()
        if res['Response'] != 'Success': return None, None, 0, 0, []
        
        df = pd.DataFrame(res['Data']['Data'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df, *predict_next_5_minutes(df)
    except: return None, None, 0, 0, []

# --- التشغيل ---
df, direction, score, conf, factors = analyze_and_predict(selected_symbol)

if df is not None:
    st.title(f"🔮 {selected_symbol} : {direction}")
    
    # الرسم البياني (تبسيط لتوفير الذاكرة)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df['time'], open=df['open'], high=df['high'], low=df['low'], close=df['close']), row=1, col=1)
    fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # إرسال التنبيه (مع حماية Try/Except)
    now_ts = time.time()
    if now_ts - st.session_state.last_signal_time[selected_symbol] >= COOLDOWN_SECONDS:
        if direction != "NEUTRAL":
            try:
                msg = f"🔮 {selected_symbol}\nالتحرك القادم: {direction}\nالثقة: {conf:.1f}%"
                bot.send_message(CHAT_ID, msg)
                st.session_state.last_signal_time[selected_symbol] = now_ts
            except Exception as e:
                st.error(f"Telegram Error: {e}")

# التحديث التلقائي
time.sleep(refresh_rate)
st.rerun()
