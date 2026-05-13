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

COOLDOWN_SECONDS = 300  # تقليل التبريد لفرص أكثر

# ═══════════════════════════════════════════════════════════════════════
# دوال المؤشرات المحسّنة (Holy Grail PRO Edition)
# ═══════════════════════════════════════════════════════════════════════

def calculate_rsi(series, period=14):
    """حساب مؤشر القوة النسبية RSI"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_mfi(df, period=14):
    """حساب مؤشر تدفق الأموال Money Flow Index"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volumeto']
    positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(window=period).sum()
    negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(window=period).sum()
    mfi = 100 - (100 / (1 + (positive_flow / negative_flow)))
    return mfi

def calculate_macd(series, fast=12, slow=26, signal=9):
    """حساب مؤشر MACD - Moving Average Convergence Divergence"""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_ema(series, period):
    """حساب المتوسط المتحرك الأسي EMA"""
    return series.ewm(span=period, adjust=False).mean()

def calculate_pivot_points(df):
    """حساب مستويات الدعم والمقاومة (Pivot Points)"""
    pivot = (df['high'] + df['low'] + df['close']) / 3
    resistance = pivot + (df['high'] - df['low'])
    support = pivot - (df['high'] - df['low'])
    return pivot, resistance, support

def calculate_volume_ma(df, period=20):
    """حساب المتوسط المتحرك للحجم"""
    return df['volumeto'].rolling(window=period).mean()

def check_signal_strength(df):
    """
    فحص قوة الإشارة وإرجاع:
    0 = لا إشارة
    1 = إشارة ضعيفة
    2 = إشارة متوسطة
    3 = إشارة قوية (💎)
    """
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # فلاتر الاتجاه
    uptrend = (last['close'] > last['EMA200'] and 
               last['EMA50'] > last['EMA200'] and 
               last['EMA20'] > last['EMA50'])
    
    downtrend = (last['close'] < last['EMA200'] and 
                 last['EMA50'] < last['EMA200'] and 
                 last['EMA20'] < last['EMA50'])
    
    # تشبع البيع والشراء
    oversold = last['RSI'] < 40 and last['MFI'] < 40
    overbought = last['RSI'] > 60 and last['MFI'] > 60
    
    # تأكيد MACD
    macd_bullish = last['MACD'] > last['MACD_Signal'] and last['MACD_Histogram'] > 0
    macd_bearish = last['MACD'] < last['MACD_Signal'] and last['MACD_Histogram'] < 0
    
    # شمعة ارتداد قوية
    bullish_candle = (last['close'] > last['open'] and 
                      (last['close'] - last['open']) > (last['high'] - last['close']) * 0.5)
    bearish_candle = (last['close'] < last['open'] and 
                      (last['open'] - last['close']) > (last['close'] - last['low']) * 0.5)
    
    # ارتداد من الدعم/المقاومة
    bounce_from_support = (last['close'] > last['Support'] and 
                           prev['close'] < last['Support'])
    bounce_from_resistance = (last['close'] < last['Resistance'] and 
                              prev['close'] > last['Resistance'])
    
    # تأكيد من الحجم
    volume_confirmation = last['volume_ma'] > 0 and last['volumeto'] > last['volume_ma'] * 1.3
    
    # --- شروط الشراء ---
    strong_buy = (uptrend and oversold and macd_bullish and 
                  bullish_candle and volume_confirmation)
    
    medium_buy = (uptrend and oversold and 
                  (macd_bullish or bullish_candle or bounce_from_support) and 
                  volume_confirmation)
    
    weak_buy = uptrend and oversold and (macd_bullish or bullish_candle)
    
    # --- شروط البيع ---
    strong_sell = (downtrend and overbought and macd_bearish and 
                   bearish_candle and volume_confirmation)
    
    medium_sell = (downtrend and overbought and 
                   (macd_bearish or bearish_candle or bounce_from_resistance) and 
                   volume_confirmation)
    
    # إرجاع نوع الإشارة
    if strong_buy:
        return 3, "BUY", "STRONG"  # 💎 STRONG BUY
    elif medium_buy:
        return 2, "BUY", "MEDIUM"  # ✅ MEDIUM BUY
    elif weak_buy:
        return 1, "BUY", "WEAK"    # ⚡ WEAK BUY
    elif strong_sell:
        return -3, "SELL", "STRONG"  # 💎 STRONG SELL
    elif medium_sell:
        return -2, "SELL", "MEDIUM"  # ✅ MEDIUM SELL
    else:
        return 0, "NEUTRAL", "NONE"

def calculate_stop_loss_take_profit(last_price, signal_type, signal_strength):
    """حساب نقاط Stop Loss و Take Profit"""
    if signal_type == "BUY":
        stop_loss = last_price * (1 - 0.02)  # 2% خسارة
        take_profit = last_price * (1 + 0.06)  # 6% ربح
    else:  # SELL
        stop_loss = last_price * (1 + 0.02)
        take_profit = last_price * (1 - 0.06)
    
    return stop_loss, take_profit

# ═══════════════════════════════════════════════════════════════════════
# واجهة المستخدم
# ═══════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="Golden Sniper PRO - 9/10", layout="wide")

col1, col2 = st.columns([3, 1])
with col1:
    st.title("🎯 نظام القناص الذهبي PRO - دقة عالية جداً")
with col2:
    st.metric("الإصدار", "9/10 ⭐", delta="محسّن")

st.markdown("---")

# الشريط الجانبي
selected_symbol = st.sidebar.selectbox("اختر الزوج", SYMBOLS)
st.sidebar.success("✅ الفلاتر المفعلة:")
st.sidebar.info("""
• EMA 20/50/200
• RSI + MFI
• MACD
• Pivot Points
• Volume Confirmation
• 3 مستويات إشارات
""")

refresh_rate = st.sidebar.slider("سرعة التحديث (ثانية)", 10, 60, 30)

# ═══════════════════════════════════════════════════════════════════════
# دالة جلب البيانات والتحليل
# ═══════════════════════════════════════════════════════════════════════

def analyze_market(symbol):
    try:
        now_ts = time.time()
        fsym = symbol[:-3] if any(x in symbol for x in ['USD', 'JPY', 'CAD']) else symbol[:3]
        tsym = symbol[-3:]
        if symbol == 'GOLD': 
            fsym, tsym = 'XAU', 'USD'

        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit=300"
        response = requests.get(url, timeout=15).json()
        
        if response['Response'] != 'Success':
            return None
        
        df = pd.DataFrame(response['Data']['Data'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # حساب جميع المؤشرات
        df['EMA200'] = calculate_ema(df['close'], 200)
        df['EMA50'] = calculate_ema(df['close'], 50)
        df['EMA20'] = calculate_ema(df['close'], 20)
        df['RSI'] = calculate_rsi(df['close'], 14)
        df['MFI'] = calculate_mfi(df, 14)
        df['MACD'], df['MACD_Signal'], df['MACD_Histogram'] = calculate_macd(df['close'])
        
        pivot, resistance, support = calculate_pivot_points(df)
        df['Pivot'] = pivot
        df['Resistance'] = resistance
        df['Support'] = support
        df['volume_ma'] = calculate_volume_ma(df, 20)
        
        return df
    except Exception as e:
        st.warning(f"خطأ في جلب البيانات: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════
# الحلقة الرئيسية
# ═══════════════════════════════════════════════════════════════════════

placeholder_metrics = st.empty()
placeholder_chart = st.empty()
placeholder_signals = st.empty()

def update_display():
    df = analyze_market(selected_symbol)
    
    if df is None or len(df) < 200:
        st.error("جاري تحميل البيانات...")
        return
    
    last_row = df.iloc[-1]
    signal_code, signal_type, signal_strength = check_signal_strength(df)
    
    # ═══════════════════════════════════════════════════════════════════════
    # عرض المقاييس
    # ═══════════════════════════════════════════════════════════════════════
    
    with placeholder_metrics.container():
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            st.metric("📊 السعر", f"${last_row['close']:.4f}")
        
        with col2:
            color_rsi = "🟢" if 30 < last_row['RSI'] < 70 else "🔴"
            st.metric(f"{color_rsi} RSI", f"{round(last_row['RSI'], 1)}")
        
        with col3:
            color_mfi = "🟢" if 30 < last_row['MFI'] < 70 else "🔴"
            st.metric(f"{color_mfi} MFI", f"{round(last_row['MFI'], 1)}")
        
        with col4:
            color_trend = "🟢" if last_row['close'] > last_row['EMA200'] else "🔴"
            trend_text = "📈 UP" if last_row['close'] > last_row['EMA200'] else "📉 DOWN"
            st.metric(f"{color_trend} الاتجاه", trend_text)
        
        with col5:
            macd_color = "🟢" if last_row['MACD'] > last_row['MACD_Signal'] else "🔴"
            st.metric(f"{macd_color} MACD", f"{round(last_row['MACD'], 4)}")
        
        with col6:
            vol_status = "🔥" if last_row['volumeto'] > last_row['volume_ma'] * 1.3 else "⚪"
            st.metric(f"{vol_status} الحجم", f"{round(last_row['volumeto'] / last_row['volume_ma'], 2)}x")
    
    # ═══════════════════════════════════════════════════════════════════════
    # الإشارات والتنبيهات
    # ═══════════════════════════════════════════════════════════════════════
    
    with placeholder_signals.container():
        if signal_code != 0:
            stop_loss, take_profit = calculate_stop_loss_take_profit(
                last_row['close'], signal_type, signal_strength
            )
            
            signal_emoji = {
                3: "💎",    # Strong
                2: "✅",    # Medium
                1: "⚡",    # Weak
                -3: "💎",
                -2: "✅",
                -1: "⚡"
            }
            
            signal_name = {
                3: "STRONG",
                2: "MEDIUM",
                1: "WEAK",
                -3: "STRONG",
                -2: "MEDIUM",
                -1: "WEAK"
            }
            
            signal_color = "green" if signal_code > 0 else "red"
            
            signal_text = f"""
            {signal_emoji.get(signal_code, '')} **إشارة {signal_name.get(abs(signal_code), '')} {signal_type}** {signal_emoji.get(signal_code, '')}
            
            🎯 السعر: **${last_row['close']:.4f}**
            🛑 Stop Loss: **${stop_loss:.4f}** (خسارة 2%)
            💰 Take Profit: **${take_profit:.4f}** (ربح 6%)
            📊 نسبة Risk/Reward: **1:{round((take_profit - last_row['close']) / (last_row['close'] - stop_loss), 2)}**
            """
            
            st.success(signal_text) if signal_code > 0 else st.error(signal_text)
            
            # إرسال تنبيه عبر Telegram
            now_ts = time.time()
            if now_ts - st.session_state.last_signal_time[selected_symbol] >= COOLDOWN_SECONDS:
                emoji_telegram = {
                    3: "💎🔥",
                    2: "✅📈",
                    1: "⚡💡",
                    -3: "💎🔥",
                    -2: "✅📉",
                    -1: "⚡💡"
                }
                
                message = f"""
{emoji_telegram.get(signal_code, '')} إشارة {signal_type} - {selected_symbol}

🎯 مستوى الإشارة: {signal_name.get(abs(signal_code))}
💵 السعر: ${last_row['close']:.4f}
🛑 Stop Loss: ${stop_loss:.4f}
💰 Take Profit: ${take_profit:.4f}

📊 المؤشرات:
• RSI: {round(last_row['RSI'], 2)}
• MFI: {round(last_row['MFI'], 2)}
• MACD: {round(last_row['MACD'], 4)}
• حجم التداول: {round(last_row['volumeto'] / last_row['volume_ma'], 2)}x

⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                
                try:
                    bot.send_message(CHAT_ID, message)
                    st.session_state.last_signal_time[selected_symbol] = now_ts
                except:
                    pass
        else:
            st.info("⏳ انتظار إشارة جديدة...")
    
    # ═══════════════════════════════════════════════════════════════════════
    # الرسم البياني المتقدم
    # ═══════════════════════════════════════════════════════════════════════
    
    with placeholder_chart.container():
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            row_heights=[0.40, 0.20, 0.20, 0.20],
            vertical_spacing=0.08,
            subplot_titles=("السعر + الاتجاهات", "MACD", "RSI", "MFI")
        )
        
        # الشموع + المتوسطات
        fig.add_trace(
            go.Candlestick(
                x=df['time'], 
                open=df['open'], 
                high=df['high'], 
                low=df['low'], 
                close=df['close'],
                name="السعر"
            ), 
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=df['time'], y=df['EMA200'], 
                      line=dict(color='white', width=2), 
                      name="EMA 200"),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=df['time'], y=df['EMA50'], 
                      line=dict(color='blue', width=1.5), 
                      name="EMA 50"),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=df['time'], y=df['EMA20'], 
                      line=dict(color='orange', width=1), 
                      name="EMA 20"),
            row=1, col=1
        )
        
        # Pivot Points
        fig.add_trace(
            go.Scatter(x=df['time'], y=df['Resistance'], 
                      line=dict(color='red', width=1, dash='dash'), 
                      name="المقاومة"),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=df['time'], y=df['Support'], 
                      line=dict(color='green', width=1, dash='dash'), 
                      name="الدعم"),
            row=1, col=1
        )
        
        # MACD
        fig.add_trace(
            go.Scatter(x=df['time'], y=df['MACD'], 
                      line=dict(color='cyan', width=2), 
                      name="MACD"),
            row=2, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=df['time'], y=df['MACD_Signal'], 
                      line=dict(color='magenta', width=1), 
                      name="Signal"),
            row=2, col=1
        )
        
        # RSI
        fig.add_trace(
            go.Scatter(x=df['time'], y=df['RSI'], 
                      line=dict(color='magenta', width=2), 
                      name="RSI"),
            row=3, col=1
        )
        
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
        fig.add_hline(y=50, line_dash="dot", line_color="gray", row=3, col=1)
        
        # MFI
        fig.add_trace(
            go.Scatter(x=df['time'], y=df['MFI'], 
                      line=dict(color='cyan', width=2), 
                      name="MFI"),
            row=4, col=1
        )
        
        fig.add_hline(y=80, line_dash="dash", line_color="red", row=4, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="green", row=4, col=1)
        fig.add_hline(y=50, line_dash="dot", line_color="gray", row=4, col=1)
        
        fig.update_layout(
            height=900,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            title=f"🎯 نظام القناص الذهبي - {selected_symbol}",
            font=dict(size=12)
        )
        
        st.plotly_chart(fig, use_container_width=True)

# تحديث الواجهة
col1, col2 = st.columns([3, 1])
with col2:
    if st.button("🔄 تحديث الآن", use_container_width=True):
        st.rerun()

update_display()

# تحديث تلقائي
import time
last_refresh = time.time()

col1, col2, col3 = st.columns(3)
with col1:
    st.info(f"⏱️ التحديث التالي بعد {refresh_rate} ثانية")
with col2:
    st.success(f"✅ آخر تحديث: {datetime.now().strftime('%H:%M:%S')}")
with col3:
    st.warning("🚀 نظام 9/10 - عالي الدقة")

# حلقة التحديث التلقائي
time.sleep(refresh_rate)
st.rerun()
