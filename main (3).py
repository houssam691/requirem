import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import telebot
import time
import requests
from datetime import datetime
import numpy as np

# --- الإعدادات ومفتاح API الخاص بك ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7' # مفتاحك الشخصي
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = [
    'BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD',
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'GOLD'
]

if 'last_signal_time' not in st.session_state:
    st.session_state.last_signal_time = {symbol: 0 for symbol in SYMBOLS}

COOLDOWN_SECONDS = 300 

# ═══════════════════════════════════════════════════════════════════════
# دوال الحسابات الفنية (النسخة الكاملة)
# ═══════════════════════════════════════════════════════════════════════

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def calculate_mfi(df, period=14):
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volumeto']
    pos = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(window=period).sum()
    neg = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(window=period).sum()
    return 100 - (100 / (1 + (pos / (neg + 1e-9))))

def calculate_macd(series):
    exp1 = series.ewm(span=12, adjust=False).mean()
    exp2 = series.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal, macd - signal

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def predict_next_5_minutes(df):
    if len(df) < 50:
        return "NEUTRAL", 0, 0, ["بيانات غير كافية"]
    
    df = df.copy()
    df['RSI'] = calculate_rsi(df['close'])
    df['MFI'] = calculate_mfi(df)
    df['MACD'], df['Signal'], df['Hist'] = calculate_macd(df['close'])
    df['EMA20'] = calculate_ema(df['close'], 20)
    df['EMA50'] = calculate_ema(df['close'], 50)
    
    last = df.iloc[-1]
    score = 0
    factors = []
    
    # منطق الاتجاه (Trend)
    if last['close'] > last['EMA20'] > last['EMA50']:
        score += 3; factors.append("✅ اتجاه صاعد قوي")
    elif last['close'] < last['EMA20'] < last['EMA50']:
        score -= 3; factors.append("❌ اتجاه هابط قوي")
        
    # منطق الزخم (Momentum)
    if last['Hist'] > 0:
        score += 2; factors.append("📈 زخم MACD إيجابي")
    else:
        score -= 2; factors.append("📉 زخم MACD سلبي")
        
    # منطق التشبع (Overbought/Oversold)
    if last['RSI'] < 30:
        score += 2; factors.append("🟢 RSI: تشبع بيعي")
    elif last['RSI'] > 70:
        score -= 2; factors.append("🔴 RSI: تشبع شرائي")

    direction = "BULLISH" if score > 2 else "BEARISH" if score < -2 else "NEUTRAL"
    confidence = min(100, (abs(score) / 10) * 100)
    
    return direction, score, confidence, factors

# ═══════════════════════════════════════════════════════════════════════
# جلب البيانات باستخدام مفتاحك API
# ═══════════════════════════════════════════════════════════════════════

def analyze_and_predict(symbol):
    try:
        s = symbol.replace("USD", "").replace("GOLD", "XAU")
        # استخدام المفتاح هنا لضمان عدم ظهور خطأ "الضغط الكبير"
        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s}&tsym=USD&limit=200&api_key={API_KEY}"
        res = requests.get(url, timeout=10).json()
        
        if res.get('Response') != 'Success':
            return None, None, None, None, None
            
        df = pd.DataFrame(res['Data']['Data'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        dir, score, conf, fact = predict_next_5_minutes(df)
        return df, dir, score, conf, fact
    except:
        return None, None, None, None, None

# ═══════════════════════════════════════════════════════════════════════
# واجهة العرض الأصلية
# ═══════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="5 Minute Predictor Pro", layout="wide")

# الهيدر
c1, c2 = st.columns([3, 1])
with c1: st.title("🔮 نظام التنبؤ الاحترافي - الـ 5 دقائق القادمة")
with c2: st.metric("النمط", "PREDICTOR 🎯", delta="API Active")

st.markdown("---")

selected_symbol = st.sidebar.selectbox("اختر الزوج", SYMBOLS)
refresh_rate = st.sidebar.slider("سرعة التحديث (ثانية)", 10, 60, 20)

# الحاويات الفارغة للتحديث
placeholder_pred = st.empty()
placeholder_metrics = st.empty()
placeholder_factors = st.empty()
placeholder_chart = st.empty()

def run_app():
    df, direction, score, confidence, factors = analyze_and_predict(selected_symbol)
    
    if df is None:
        st.error("⚠️ جاري جلب البيانات... تأكد من استقرار الإنترنت")
        return

    # 1. عرض التنبؤ الكبير
    with placeholder_pred.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if direction == "BULLISH":
                st.success(f"### 📈 الحركة القادمة: **BULLISH** ({confidence:.1f}%)")
            elif direction == "BEARISH":
                st.error(f"### 📉 الحركة القادمة: **BEARISH** ({confidence:.1f}%)")
            else:
                st.warning("### 〰️ الحركة القادمة: **NEUTRAL**")

    # 2. المقاييس
    with placeholder_metrics.container():
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📊 السعر", f"${df['close'].iloc[-1]:.4f}")
        m2.metric("🎯 الثقة", f"{confidence:.1f}%")
        m3.metric("🔥 القوة", f"{score:.1f}/10")
        m4.metric("🕒 الوقت", datetime.now().strftime('%H:%M:%S'))

    # 3. العوامل المؤثرة
    with placeholder_factors.container():
        st.subheader("📊 العوامل المؤثرة:")
        cols = st.columns(2)
        for i, f in enumerate(factors):
            with cols[i % 2]: st.info(f)

    # 4. الرسم البياني الكامل
    with placeholder_chart.container():
        df_chart = df.copy()
        df_chart['EMA20'] = calculate_ema(df_chart['close'], 20)
        df_chart['RSI'] = calculate_rsi(df_chart['close'])
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df_chart['time'], open=df_chart['open'], high=df_chart['high'], low=df_chart['low'], close=df_chart['close'], name="Price"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_chart['time'], y=df_chart['EMA20'], line=dict(color='orange'), name="EMA 20"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_chart['time'], y=df_chart['RSI'], line=dict(color='magenta'), name="RSI"), row=2, col=1)
        
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    # 5. تنبيه تلغرام
    now = time.time()
    if direction != "NEUTRAL" and (now - st.session_state.last_signal_time[selected_symbol] >= COOLDOWN_SECONDS):
        try:
            msg = f"🔮 {selected_symbol}\nتوقع: {direction}\nثقة: {confidence:.1f}%"
            bot.send_message(CHAT_ID, msg)
            st.session_state.last_signal_time[selected_symbol] = now
        except: pass

run_app()
time.sleep(refresh_rate)
st.rerun()
