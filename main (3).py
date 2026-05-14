import streamlit as st
import pandas as pd
import telebot
import time
import requests
from datetime import datetime, timedelta, timezone

# --- الإعدادات ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'

try:
    bot = telebot.TeleBot(TOKEN, threaded=False)
except Exception as e:
    print(f"خطأ في الاتصال بـ Telegram: {e}")
    bot = None

SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'GOLD']

# --- دالة الاستراتيجية ---
def real_opportunity_strategy(df):
    """
    تحليل باستخدام:
    - EMA 200: المتوسط المتحرك الأسي
    - RSI: مؤشر القوة النسبية
    """
    try:
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        last_row = df.iloc[-1]
        
        if last_row['close'] > last_row['ema200'] and last_row['rsi'] < 30:
            return "BUY", 85
        elif last_row['close'] < last_row['ema200'] and last_row['rsi'] > 70:
            return "SELL", 85
        return "NEUTRAL", 0
    except Exception as e:
        print(f"خطأ في الاستراتيجية: {e}")
        return "NEUTRAL", 0

# --- إدارة الحالة ---
if 'last_hour_sent' not in st.session_state:
    st.session_state.last_hour_sent = None
if 'tracker' not in st.session_state:
    st.session_state.tracker = {symbol: 0 for symbol in SYMBOLS}
if 'signal_count' not in st.session_state:
    st.session_state.signal_count = 0

# --- إعدادات Streamlit ---
st.set_page_config(page_title="Trading Bot", layout="wide")
st.title("⏳ نظام التداول الآلي")

# --- عرض المعلومات ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    current_time = datetime.now(timezone.utc) + timedelta(hours=1)
    st.metric("الوقت الآن", current_time.strftime("%H:%M:%S"))
with col2:
    st.metric("عدد العملات", len(SYMBOLS))
with col3:
    st.metric("حالة البوت", "🟢 يعمل" if bot else "🔴 متوقف")
with col4:
    st.metric("عدد الإشارات", st.session_state.signal_count)

st.divider()

# --- منطق رسالة واحدة كل ساعة بثواني 00:00 ---
current_time = datetime.now(timezone.utc) + timedelta(hours=1)  # UTC+1
current_hour = current_time.hour
current_minute = current_time.minute
current_second = current_time.second

# فحص: هل نحن في الثانية 00 من الدقيقة 00؟
if current_minute == 0 and current_second == 0:
    # هل هذه ساعة جديدة لم نرسل فيها رسالة؟
    if st.session_state.last_hour_sent != current_hour:
        display_time = current_time.strftime("%H:%M:%S")
        message = f"✅ نظام التداول يعمل\n⏰ الوقت: {display_time}"
        
        if bot:
            try:
                bot.send_message(CHAT_ID, message)
                st.success(f"✅ تم إرسال الرسالة في {display_time}")
            except Exception as e:
                st.error(f"❌ خطأ في الإرسال: {e}")
        
        st.session_state.last_hour_sent = current_hour

# --- تحليل العملات ---
st.subheader("📊 تحليل العملات")

analysis_placeholder = st.container()

for sym in SYMBOLS:
    s_name = sym.replace("USD", "").replace("GOLD", "XAU")
    url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s_name}&tsym=USD&limit=250&api_key={API_KEY}"
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # تحقق من الأخطاء
        
        res = response.json()
        
        if 'Data' not in res or 'Data' not in res['Data']:
            continue
        
        df = pd.DataFrame(res['Data']['Data'])
        
        if df.empty:
            continue
        
        decision, conf = real_opportunity_strategy(df)
        
        # فحص الإشارات القوية
        if decision != "NEUTRAL" and (time.time() - st.session_state.tracker[sym] > 600):
            emoji = '🟢' if decision == 'BUY' else '🔴'
            trend = 'صعود' if decision == 'BUY' else 'هبوط'
            
            msg = f"🎯 **إشارة: {sym}**\n{emoji} **الاتجاه:** {trend}\n💪 **الثقة:** {conf}%"
            
            if bot:
                try:
                    bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                    st.session_state.signal_count += 1
                except Exception as e:
                    print(f"خطأ في إرسال الإشارة {sym}: {e}")
            
            st.session_state.tracker[sym] = time.time()
            
            # عرض الإشارة في الواجهة
            with analysis_placeholder:
                st.warning(f"{emoji} **{sym}**: إشارة {trend} (ثقة: {conf}%)")
    
    except requests.exceptions.RequestException as e:
        print(f"خطأ في جلب بيانات {sym}: {e}")
        continue
    except Exception as e:
        print(f"خطأ في معالجة {sym}: {e}")
        continue

# --- معلومات إضافية ---
st.divider()
with st.expander("ℹ️ معلومات عن الاستراتيجية"):
    st.markdown("""
    ### 📈 كيفية عمل الاستراتيجية:
    
    **1. المتوسط المتحرك الأسي (EMA 200)**
    - يحدد الاتجاه العام للسعر
    - السعر أعلى من EMA = اتجاه صعودي
    - السعر أقل من EMA = اتجاه هبوطي
    
    **2. مؤشر القوة النسبية (RSI)**
    - يكتشف الأسعار الشديدة
    - RSI < 30 = بيع مفرط (فرصة شراء)
    - RSI > 70 = شراء مفرط (فرصة بيع)
    
    **3. القرار النهائي**
    - **BUY**: السعر فوق EMA و RSI < 30
    - **SELL**: السعر تحت EMA و RSI > 70
    - **NEUTRAL**: لا توجد فرصة قوية
    """)

# --- الانتظار وإعادة التشغيل ---
time.sleep(1)
st.rerun()
