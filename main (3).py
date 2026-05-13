import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import telebot
import time
import requests
from datetime import datetime, date

# --- إعداداتك الأصلية (لم يتم تغييرها) ---
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
if 'last_heartbeat_hour' not in st.session_state:
    st.session_state.last_heartbeat_hour = -1

# --- الميزة الجديدة: إرسال رسالة الترحيب مرة واحدة فقط في اليوم ---
if 'last_welcome_date' not in st.session_state:
    try:
        today_date = date.today().strftime('%Y-%m-%d')
        bot.send_message(CHAT_ID, f"🛡️ تم تشغيل المنصة بنجاح.\n📅 التاريخ: {today_date}\n✅ البوت يراقب السوق الآن.")
        st.session_state.last_welcome_date = today_date
    except:
        pass

# --- دوالك الأصلية (بدون تغيير) ---
def calculate_rsi(series, period=14):
    try:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    except:
        return pd.Series([50] * len(series))

# --- إعدادات واجهة Streamlit الاحترافية ---
st.set_page_config(page_title="Pro Trading Dashboard", layout="wide")
st.title("🛡️ منصة المراقبة والتحليل اللحظي")

# القائمة الجانبية للاختيار
selected_symbol = st.sidebar.selectbox("اختر الزوج للعرض البياني", SYMBOLS)
st.sidebar.markdown("---")
st.sidebar.write("✅ البوت يراقب جميع العملات في الخلفية")

# أماكن عرض البيانات في الواجهة
metrics_col = st.columns(3)
chart_placeholder = st.empty()

# دالة الفحص المدمجة مع الواجهة
def check_market_with_ui(symbol, is_viewed=False):
    try:
        current_time = time.time()
        
        fsym = symbol[:-3] if any(x in symbol for x in ['USD', 'JPY', 'CAD']) else symbol[:3]
        tsym = symbol[-3:]
        if symbol == 'GOLD': fsym, tsym = 'XAU', 'USD'

        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit=50"
        response = requests.get(url, timeout=15).json()
        
        if 'Data' not in response or 'Data' not in response['Data'] or not response['Data']['Data']:
            return None
            
        df = pd.DataFrame(response['Data']['Data'])
        if len(df) < 30: return None
        
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df['EMA'] = df['close'].ewm(span=50, adjust=False).mean()
        df['RSI'] = calculate_rsi(df['close'])
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # تنفيذ منطق الإشارات الخاص بك
        if current_time - st.session_state.last_signal_time[symbol] >= COOLDOWN_SECONDS:
            if last['close'] > last['EMA'] and prev['RSI'] < 30 and last['RSI'] >= 30:
                bot.send_message(CHAT_ID, f"🎯 فرصة صعود: {symbol}\n📈 RSI: {round(last['RSI'], 2)}")
                st.session_state.last_signal_time[symbol] = current_time
            elif last['close'] < last['EMA'] and prev['RSI'] > 70 and last['RSI'] <= 70:
                bot.send_message(CHAT_ID, f"🎯 فرصة هبوط: {symbol}\n📉 RSI: {round(last['RSI'], 2)}")
                st.session_state.last_signal_time[symbol] = current_time
        
        return df
    except Exception as e:
        st.error(f"⚠️ خطأ في {symbol}: {e}")
        return None

# حلقة التشغيل الأساسية للموقع
while True:
    # 1. فحص رسالة النبض (Heartbeat) - تبقى كل ساعة كما هي
    current_hour = datetime.now().hour
    if current_hour != st.session_state.last_heartbeat_hour:
        try:
            bot.send_message(CHAT_ID, f"✅ نبض البوت: أنا أعمل حالياً وأراقب {len(SYMBOLS)} زوجاً.\n⏰ الوقت: {datetime.now().strftime('%H:%M')}")
            st.session_state.last_heartbeat_hour = current_hour
        except: pass

    # 2. تحديث الواجهة والرسوم البيانية للزوج المختار
    for s in SYMBOLS:
        is_viewed = (s == selected_symbol)
        df_result = check_market_with_ui(s, is_viewed)
        
        if is_viewed and df_result is not None:
            last_row = df_result.iloc[-1]
            
            # تحديث الـ Metrics
            metrics_col[0].metric("السعر الحالي", f"${last_row['close']}")
            metrics_col[1].metric("RSI", round(last_row['RSI'], 2))
            metrics_col[2].metric("الاتجاه", "صاعد" if last_row['close'] > last_row['EMA'] else "هابط")

            # رسم الشارت الاحترافي
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df_result['time'], open=df_result['open'], high=df_result['high'], low=df_result['low'], close=df_result['close'], name="السعر"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_result['time'], y=df_result['EMA'], line=dict(color='orange', width=2), name="EMA 50"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_result['time'], y=df_result['RSI'], line=dict(color='magenta', width=1.5), name="RSI"), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
            
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
            chart_placeholder.plotly_chart(fig, use_container_width=True)
            
        time.sleep(0.5)
