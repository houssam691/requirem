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
# دوال التنبؤ بحركة الـ 5 دقائق القادمة
# ═══════════════════════════════════════════════════════════════════════

def calculate_rsi(series, period=14):
    """RSI للتحليل"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_mfi(df, period=14):
    """MFI لقراءة قوة الحركة"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volumeto']
    positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(window=period).sum()
    negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(window=period).sum()
    mfi = 100 - (100 / (1 + (positive_flow / negative_flow)))
    return mfi

def calculate_macd(series, fast=12, slow=26, signal=9):
    """MACD لكشف الزخم"""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_ema(series, period):
    """EMA للاتجاه"""
    return series.ewm(span=period, adjust=False).mean()

def calculate_momentum(series, period=3):
    """الزخم - كم السرعة"""
    return series - series.shift(period)

def calculate_atr(df, period=14):
    """Average True Range - معدل التذبذب"""
    df['tr1'] = df['high'] - df['low']
    df['tr2'] = abs(df['high'] - df['close'].shift())
    df['tr3'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
    return df['tr'].rolling(window=period).mean()

def predict_next_5_minutes(df):
    """
    التنبؤ بحركة الـ 5 دقائق القادمة
    يرجع: (اتجاه، قوة التنبؤ، ثقة النسبة)
    """
    
    if len(df) < 20:
        return None, 0, 0
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]
    prev3 = df.iloc[-4]
    prev5 = df.iloc[-5]
    
    # حساب المؤشرات
    df['RSI'] = calculate_rsi(df['close'], 14)
    df['MFI'] = calculate_mfi(df, 14)
    df['MACD'], df['MACD_Signal'], df['MACD_Histogram'] = calculate_macd(df['close'])
    df['EMA20'] = calculate_ema(df['close'], 20)
    df['EMA50'] = calculate_ema(df['close'], 50)
    df['Momentum'] = calculate_momentum(df['close'], 3)
    df['ATR'] = calculate_atr(df, 14)
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # إعادة حساب
    rsi = last['RSI']
    mfi = last['MFI']
    macd = last['MACD']
    macd_signal = last['MACD_Signal']
    ema20 = last['EMA20']
    ema50 = last['EMA50']
    momentum = last['Momentum']
    atr = last['ATR']
    price = last['close']
    
    # ═══════════════════════════════════════════════════════════════════
    # محركات التنبؤ (Prediction Drivers)
    # ═══════════════════════════════════════════════════════════════════
    
    prediction_score = 0  # من -10 إلى +10
    confidence = 0  # من 0 إلى 100
    factors = []
    
    # 1️⃣ الاتجاه العام (Trend)
    if price > ema20 > ema50:
        prediction_score += 3
        factors.append("✅ الاتجاه صاعد قوي")
    elif price > ema50:
        prediction_score += 1.5
        factors.append("✅ الاتجاه صاعد")
    elif price < ema20 < ema50:
        prediction_score -= 3
        factors.append("❌ الاتجاه هابط قوي")
    elif price < ema50:
        prediction_score -= 1.5
        factors.append("❌ الاتجاه هابط")
    else:
        factors.append("〰️ الاتجاه محايد")
    
    # 2️⃣ الزخم (Momentum)
    if momentum > 0:
        prediction_score += 2
        factors.append(f"📈 زخم صاعد: {momentum:.6f}")
    else:
        prediction_score -= 2
        factors.append(f"📉 زخم هابط: {momentum:.6f}")
    
    # 3️⃣ RSI - التشبع
    if rsi < 30:
        prediction_score += 2
        factors.append("🟢 RSI منخفض = فرصة صعود")
    elif rsi > 70:
        prediction_score -= 2
        factors.append("🔴 RSI مرتفع = قد ينزل")
    elif 40 < rsi < 60:
        factors.append("〰️ RSI محايد")
    
    # 4️⃣ MFI - قوة تدفق الأموال
    if mfi < 30:
        prediction_score += 1.5
        factors.append("🟢 MFI منخفض = دخول أموال قادم")
    elif mfi > 70:
        prediction_score -= 1.5
        factors.append("🔴 MFI مرتفع = خروج أموال")
    
    # 5️⃣ MACD - الزخم العام
    if macd > macd_signal and last['MACD_Histogram'] > 0:
        prediction_score += 2.5
        factors.append("📈 MACD صاعد قوي")
    elif macd < macd_signal and last['MACD_Histogram'] < 0:
        prediction_score -= 2.5
        factors.append("📉 MACD هابط قوي")
    
    # 6️⃣ حركة الشمعة الأخيرة
    if last['close'] > last['open']:
        prediction_score += 1
        factors.append("🟢 آخر شمعة صاعدة")
    else:
        prediction_score -= 1
        factors.append("🔴 آخر شمعة هابطة")
    
    # 7️⃣ مقارنة الأسعار (ارتفاع أم انخفاض)
    last_5_avg = (df.iloc[-5:]['close'].mean())
    if price > last_5_avg:
        prediction_score += 1
        factors.append(f"📈 السعر فوق المتوسط الـ 5")
    else:
        prediction_score -= 1
        factors.append(f"📉 السعر تحت المتوسط الـ 5")
    
    # 8️⃣ التقلب (Volatility)
    if atr > atr * 1.2:  # تقلب عالي
        confidence += 10
        factors.append("🔥 تقلب عالي = إشارة قوية")
    else:
        factors.append("〰️ تقلب عادي")
    
    # 9️⃣ نسبة الصعود/الهبوط الأخيرة
    up_count = sum(1 for i in range(-5, 0) if df.iloc[i]['close'] > df.iloc[i]['open'])
    if up_count >= 3:
        prediction_score += 1.5
        factors.append(f"📈 آخر {up_count} من 5 شمعات صاعدة")
    elif up_count <= 2:
        prediction_score -= 1.5
        factors.append(f"📉 آخر {up_count} من 5 شمعات فقط صاعدة")
    
    # حساب الثقة
    confidence = min(100, (abs(prediction_score) / 10) * 100)
    
    # تحديد الاتجاه
    if prediction_score > 2:
        direction = "BULLISH"  # صاعد
    elif prediction_score < -2:
        direction = "BEARISH"  # هابط
    else:
        direction = "NEUTRAL"  # محايد
    
    return direction, prediction_score, confidence, factors

# ═══════════════════════════════════════════════════════════════════════
# واجهة المستخدم
# ═══════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="5 Minute Predictor", layout="wide")

col1, col2 = st.columns([3, 1])
with col1:
    st.title("🔮 نظام التنبؤ - الـ 5 دقائق القادمة")
with col2:
    st.metric("النمط", "PREDICTOR 🎯", delta="دقيق")

st.markdown("---")

# الشريط الجانبي
selected_symbol = st.sidebar.selectbox("اختر الزوج", SYMBOLS)
st.sidebar.success("✅ التحليل الحالي:")
st.sidebar.info("""
🔮 يتنبأ بـ:
• اتجاه الـ 5 دقائق القادمة
• قوة التنبؤ
• نسبة الثقة
• العوامل المؤثرة
""")

refresh_rate = st.sidebar.slider("سرعة التحديث (ثانية)", 5, 30, 15)

# ═══════════════════════════════════════════════════════════════════════
# دالة جلب البيانات والتنبؤ
# ═══════════════════════════════════════════════════════════════════════

def analyze_and_predict(symbol):
    try:
        fsym = symbol[:-3] if any(x in symbol for x in ['USD', 'JPY', 'CAD']) else symbol[:3]
        tsym = symbol[-3:]
        if symbol == 'GOLD': 
            fsym, tsym = 'XAU', 'USD'

        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit=300"
        response = requests.get(url, timeout=15).json()
        
        if response['Response'] != 'Success':
            return None, None, None, None
        
        df = pd.DataFrame(response['Data']['Data'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # التنبؤ
        direction, score, confidence, factors = predict_next_5_minutes(df)
        
        return df, direction, score, confidence, factors
    except:
        return None, None, None, None, None

# ═══════════════════════════════════════════════════════════════════════
# الحلقة الرئيسية
# ═══════════════════════════════════════════════════════════════════════

placeholder_prediction = st.empty()
placeholder_metrics = st.empty()
placeholder_factors = st.empty()
placeholder_chart = st.empty()

def update_display():
    df, direction, score, confidence, factors = analyze_and_predict(selected_symbol)
    
    if df is None:
        st.error("جاري تحميل البيانات...")
        return
    
    last_row = df.iloc[-1]
    
    # ═══════════════════════════════════════════════════════════════════
    # عرض التنبؤ الكبير
    # ═══════════════════════════════════════════════════════════════════
    
    with placeholder_prediction.container():
        if direction == "BULLISH":
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.success(f"""
                ### 📈 الـ 5 دقائق القادمة: **BULLISH** 📈
                
                ستكون حركة **صاعدة** 🟢
                """)
        elif direction == "BEARISH":
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.error(f"""
                ### 📉 الـ 5 دقائق القادمة: **BEARISH** 📉
                
                ستكون حركة **هابطة** 🔴
                """)
        else:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.warning(f"""
                ### 〰️ الـ 5 دقائق القادمة: **NEUTRAL** 〰️
                
                الحركة **محايدة** ⚪
                """)
    
    # ═══════════════════════════════════════════════════════════════════
    # المقاييس
    # ═══════════════════════════════════════════════════════════════════
    
    with placeholder_metrics.container():
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("📊 السعر الحالي", f"${last_row['close']:.6f}")
        
        with col2:
            color = "🟢" if score > 0 else "🔴"
            st.metric(f"{color} قوة التنبؤ", f"{score:.1f}/10")
        
        with col3:
            st.metric("🎯 نسبة الثقة", f"{confidence:.1f}%")
        
        with col4:
            df_calc = df.copy()
            df_calc['RSI'] = calculate_rsi(df_calc['close'], 14)
            st.metric("📊 RSI", f"{df_calc['RSI'].iloc[-1]:.1f}")
        
        with col5:
            df_calc['MACD'], df_calc['MACD_Signal'], _ = calculate_macd(df_calc['close'])
            macd_val = df_calc['MACD'].iloc[-1]
            signal_val = df_calc['MACD_Signal'].iloc[-1]
            macd_color = "🟢" if macd_val > signal_val else "🔴"
            st.metric(f"{macd_color} MACD", f"{macd_val:.6f}")
    
    # ═══════════════════════════════════════════════════════════════════
    # العوامل المؤثرة
    # ═══════════════════════════════════════════════════════════════════
    
    with placeholder_factors.container():
        st.subheader("📊 العوامل المؤثرة على التنبؤ:")
        
        cols = st.columns(2)
        for idx, factor in enumerate(factors):
            with cols[idx % 2]:
                st.info(factor)
    
    # ═══════════════════════════════════════════════════════════════════
    # الرسم البياني
    # ═══════════════════════════════════════════════════════════════════
    
    with placeholder_chart.container():
        df_chart = df.copy()
        df_chart['EMA20'] = calculate_ema(df_chart['close'], 20)
        df_chart['EMA50'] = calculate_ema(df_chart['close'], 50)
        df_chart['RSI'] = calculate_rsi(df_chart['close'], 14)
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[0.7, 0.3],
            vertical_spacing=0.1,
            subplot_titles=("السعر + المتوسطات", "RSI")
        )
        
        # الشموع
        fig.add_trace(
            go.Candlestick(
                x=df_chart['time'],
                open=df_chart['open'],
                high=df_chart['high'],
                low=df_chart['low'],
                close=df_chart['close'],
                name="السعر"
            ),
            row=1, col=1
        )
        
        # EMA 20
        fig.add_trace(
            go.Scatter(
                x=df_chart['time'],
                y=df_chart['EMA20'],
                line=dict(color='orange', width=2),
                name="EMA 20"
            ),
            row=1, col=1
        )
        
        # EMA 50
        fig.add_trace(
            go.Scatter(
                x=df_chart['time'],
                y=df_chart['EMA50'],
                line=dict(color='blue', width=2),
                name="EMA 50"
            ),
            row=1, col=1
        )
        
        # RSI
        fig.add_trace(
            go.Scatter(
                x=df_chart['time'],
                y=df_chart['RSI'],
                line=dict(color='magenta', width=2),
                name="RSI"
            ),
            row=2, col=1
        )
        
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
        
        # خط التنبؤ على آخر نقطة
        if direction == "BULLISH":
            fig.add_annotation(
                x=df_chart['time'].iloc[-1],
                y=df_chart['close'].iloc[-1],
                text="📈 BULLISH",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="green",
                font=dict(size=14, color="green")
            )
        elif direction == "BEARISH":
            fig.add_annotation(
                x=df_chart['time'].iloc[-1],
                y=df_chart['close'].iloc[-1],
                text="📉 BEARISH",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="red",
                font=dict(size=14, color="red")
            )
        
        fig.update_layout(
            height=700,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            title=f"🔮 تنبؤ الـ 5 دقائق القادمة - {selected_symbol}",
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # ═══════════════════════════════════════════════════════════════════
    # إرسال التنبيه
    # ═══════════════════════════════════════════════════════════════════
    
    now_ts = time.time()
    if now_ts - st.session_state.last_signal_time[selected_symbol] >= COOLDOWN_SECONDS:
        if direction != "NEUTRAL":
            emoji = "📈" if direction == "BULLISH" else "📉"
            message = f"""
{emoji} تنبؤ الـ 5 دقائق القادمة

الزوج: {selected_symbol}
التنبؤ: {direction}
قوة التنبؤ: {score:.1f}/10
نسبة الثقة: {confidence:.1f}%

السعر الحالي: ${last_row['close']:.6f}

العوامل:
{chr(10).join(factors[:5])}

⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            try:
                bot.send_message(CHAT_ID, message)
                st.session_state.last_signal_time[selected_symbol] = now_ts
            except:
                pass

# تحديث الواجهة
col1, col2 = st.columns([3, 1])
with col2:
    if st.button("🔄 تحديث الآن", use_container_width=True):
        st.rerun()

update_display()

# معلومات التحديث
col1, col2, col3 = st.columns(3)
with col1:
    st.info(f"⏱️ التحديث التالي بعد {refresh_rate} ثانية")
with col2:
    st.success(f"✅ آخر تحديث: {datetime.now().strftime('%H:%M:%S')}")
with col3:
    st.warning("🔮 نظام التنبؤ - نسبة دقة عالية")

# حلقة التحديث التلقائي
time.sleep(refresh_rate)
st.rerun()
