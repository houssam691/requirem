import streamlit as st
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from datetime import datetime

# --- الإعدادات ومفتاح الأمان ---
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'
SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'EURUSD', 'GOLD']

def get_data_with_key(symbol):
    """جلب البيانات باستخدام مفتاح الـ API الخاص بك لضمان الاستقرار"""
    try:
        # تجهيز الرموز
        s = symbol.replace("USD", "").replace("GOLD", "XAU")
        
        # الرابط المحدث مع مفتاحك الخاص
        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s}&tsym=USD&limit=60&api_key={API_KEY}"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('Response') == 'Success':
            df = pd.DataFrame(data['Data']['Data'])
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        else:
            st.sidebar.error(f"خطأ من المزود: {data.get('Message')}")
            return None
    except Exception as e:
        st.sidebar.error(f"خطأ في الاتصال: {e}")
        return None

# --- واجهة المستخدم ---
st.set_page_config(page_title="Pro Trader Predictor", layout="wide")

st.title("🚀 نظام التداول الاحترافي (مفتاح API مفعل)")

selected = st.sidebar.selectbox("اختر الزوج للتداول", SYMBOLS)
refresh_rate = st.sidebar.slider("سرعة التحديث (ثانية)", 10, 60, 20)

# جلب البيانات
df = get_data_with_key(selected)

if df is not None:
    # حسابات سريعة للتنبؤ
    last_price = df['close'].iloc[-1]
    prev_price = df['close'].iloc[-2]
    change = last_price - prev_price
    
    # حساب RSI مبسط للدقة
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs.iloc[-1]))

    # عرض المقاييس
    col1, col2, col3 = st.columns(3)
    col1.metric("السعر الحالي", f"${last_price:,.2f}", f"{change:,.4f}")
    col2.metric("مؤشر RSI", f"{rsi:.2f}")
    col3.metric("آخر تحديث", datetime.now().strftime('%H:%M:%S'))

    # منطق التوصية
    st.markdown("---")
    if rsi < 35:
        st.success("🟢 إشارة قوية: شراء (تشبع بيعي)")
    elif rsi > 65:
        st.error("🔴 إشارة قوية: بيع (تشبع شرائي)")
    elif change > 0:
        st.info("📈 اتجاه صاعد حالي")
    else:
        st.warning("📉 اتجاه هابط حالي")

    # الرسم البياني الاحترافي
    fig = go.Figure(data=[go.Candlestick(
        x=df['time'],
        open=df['open'], high=df['high'],
        low=df['low'], close=df['close'],
        name=selected
    )])
    
    fig.update_layout(
        template="plotly_dark", 
        height=500, 
        xaxis_rangeslider_visible=False,
        title=f"حركة سعر {selected} في آخر ساعة"
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("⚠️ لم يتم استلام بيانات. تأكد من تفعيل مفتاح API الخاص بك.")

# التحديث التلقائي
time.sleep(refresh_rate)
st.rerun()
