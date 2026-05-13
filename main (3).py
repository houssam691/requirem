import streamlit as st
import pandas as pd
import requests
import time
import plotly.graph_objects as go

# --- الإعدادات ---
SYMBOLS = ['BTCUSD', 'ETHUSD', 'BNBUSD', 'EURUSD', 'GOLD']

def get_data_safe(symbol):
    """دالة جلب بيانات فائقة الاستقرار"""
    try:
        # تحويل الرموز لتناسب الـ API
        s = symbol.replace("USD", "").replace("GOLD", "XAU")
        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={s}&tsym=USD&limit=50"
        
        # إضافة Timeout قصير لعدم تعليق الموقع
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if data.get('Response') == 'Success':
            df = pd.DataFrame(data['Data']['Data'])
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        return None
    except:
        return None

# --- واجهة المستخدم ---
st.set_page_config(page_title="Trader Predictor", layout="wide")
st.title("🚀 نظام التداول المستقر")

selected = st.sidebar.selectbox("اختر العملة", SYMBOLS)

# محاولة جلب البيانات
df = get_data_safe(selected)

if df is not None:
    # حساب مؤشر بسيط للتأكد من العمل
    last_price = df['close'].iloc[-1]
    prev_price = df['close'].iloc[-2]
    change = last_price - prev_price
    
    col1, col2 = st.columns(2)
    col1.metric("السعر الحالي", f"${last_price:,.2f}", f"{change:,.4f}")
    
    # تحديد التوصية
    if change > 0:
        st.success("📈 الإشارة الحالية: شراء (صعود قصير المدى)")
    else:
        st.error("📉 الإشارة الحالية: بيع (هبوط قصير المدى)")

    # الرسم البياني
    fig = go.Figure(data=[go.Candlestick(x=df['time'],
                open=df['open'], high=df['high'],
                low=df['low'], close=df['close'])])
    fig.update_layout(template="plotly_dark", height=400, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("❌ عذراً، هناك ضغط كبير على مزود البيانات حالياً.")
    st.info("💡 نصيحة: انتظر 10 ثوانٍ وسيتم التحديث تلقائياً، أو تأكد من أنك لم تتجاوز حد الطلبات المجانية.")

# التحديث التلقائي
time.sleep(15)
st.rerun()
