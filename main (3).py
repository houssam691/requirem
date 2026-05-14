import streamlit as st
import pandas as pd
import telebot
import time
import requests
from datetime import datetime, timedelta, timezone
import numpy as np
from collections import deque

# --- إعدادات التليجرام ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
API_KEY = 'e507283f6d2ebbc351b5f1c21763036c538121b0dc331208902672d897c7aab7'

try:
    bot = telebot.TeleBot(TOKEN, threaded=False)
except:
    bot = None

# --- قائمة الأزواج ---
SYMBOLS = [
    'BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD', 'GOLD',
    'GBPAUD', 'EURAUD', 'USDCAD', 'CHFJPY', 'USDJPY', 'USDCHF', 'GBPCAD',
    'EURCAD', 'GBPJPY', 'CADJPY', 'EURGBP', 'EURJPY', 'GBPCHF', 'GBPUSD',
    'EURCHF', 'EURUSD', 'AUDCAD', 'AUDJPY', 'AUDCHF', 'AUDUSD'
]

# --- كلاس لحساب الوقت الذكي ---
class SmartTimer:
    def __init__(self):
        self.history = {}  # {symbol: {'durations': [], 'success': []}}
        
    def add_result(self, symbol, duration_minutes, success):
        if symbol not in self.history:
            self.history[symbol] = {'durations': [], 'success': []}
        self.history[symbol]['durations'].append(duration_minutes)
        self.history[symbol]['success'].append(success)
        
        # الاحتفاظ بآخر 50 صفقة فقط
        if len(self.history[symbol]['durations']) > 50:
            self.history[symbol]['durations'] = self.history[symbol]['durations'][-50:]
            self.history[symbol]['success'] = self.history[symbol]['success'][-50:]
    
    def calculate_duration(self, symbol, signal_type, volatility):
        # حساب الوقت بناءً على:
        # 1. التقلب الحالي (كلما زاد التقلب قلت المدة)
        # 2. التاريخ السابق للزوج (إن وجد)
        
        base_time = 10  # 10 دقائق أساسية
        
        # تعديل حسب التقلب
        if volatility > 0.3:
            volatility_factor = 0.6  # تقليل الوقت لارتفاع التقلب
        elif volatility > 0.2:
            volatility_factor = 0.8
        elif volatility > 0.1:
            volatility_factor = 1.0
        else:
            volatility_factor = 1.2  # زيادة الوقت لانخفاض التقلب
        
        optimal = base_time * volatility_factor
        
        # إذا كان لدينا تاريخ للزوج
        if symbol in self.history and len(self.history[symbol]['durations']) > 5:
            # حساب متوسط مدة الصفقات الناجحة فقط
            successful_durations = [
                d for d, s in zip(self.history[symbol]['durations'], self.history[symbol]['success']) 
                if s == True
            ]
            if successful_durations:
                avg_history = np.mean(successful_durations)
                optimal = (optimal * 0.6) + (avg_history * 0.4)  # 60% حالياً، 40% تاريخي
        
        # تحديد المدة بين 3 و 20 دقيقة
        optimal = max(3, min(20, optimal))
        
        minutes = int(optimal)
        seconds = int((optimal - minutes) * 60)
        
        return f"{minutes:02d}:{seconds:02d}", optimal

smart_timer = SmartTimer()

# --- الاستراتيجية السريعة ---
def get_signal_fast(df_1m, df_5m):
    try:
        # اتجاه 5 دقائق
        df_5m['ema200'] = df_5m['close'].ewm(span=200, adjust=False).mean()
        trend = "UP" if df_5m['close'].iloc[-1] > df_5m['ema200'].iloc[-1] else "DOWN"
        
        # RSI سريع
        delta = df_1m['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # ATR للتقلب
        df_1m['tr'] = np.maximum(
            df_1m['high'] - df_1m['low'],
            np.maximum(abs(df_1m['high'] - df_1m['close'].shift(1)),
                      abs(df_1m['low'] - df_1m['close'].shift(1)))
        )
        atr = df_1m['tr'].rolling(window=14).mean().iloc[-1]
        current_price = df_1m['close'].iloc[-1]
        volatility = (atr / current_price) * 100
        
        prev_rsi = rsi.iloc[-2]
        curr_rsi = rsi.iloc[-1]
        is_bullish = current_price > df_1m['open'].iloc[-1]
        
        signal = "NEUTRAL"
        confidence = 0
        
        if trend == "UP" and prev_rsi < 30 and curr_rsi >= 30 and is_bullish:
            signal = "BUY"
            confidence = 85 + (5 if volatility < 0.15 else 0)
        elif trend == "DOWN" and prev_rsi > 70 and curr_rsi <= 70 and not is_bullish:
            signal = "SELL"
            confidence = 85 + (5 if volatility < 0.15 else 0)
        
        return signal, confidence, current_price, volatility, curr_rsi
        
    except:
        return "NEUTRAL", 0, 0, 0, 0

# --- واجهة Streamlit ---
st.set_page_config(page_title="⚡ نظام الإشارات السريع", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .big-number {
        font-size: 48px;
        font-weight: bold;
        text-align: center;
    }
    .scan-status {
        background-color: #1e1e1e;
        padding: 10px;
        border-radius: 10px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# Header
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.title("⚡ نظام الإشارات السريع")
with col2:
    current_time = datetime.now(timezone.utc) + timedelta(hours=1)
    st.metric("🕐 الوقت", current_time.strftime("%H:%M:%S"))
with col3:
    if 'scan_count' not in st.session_state:
        st.session_state.scan_count = 0
    st.metric("🔄 فحص رقم", st.session_state.scan_count)
with col4:
    st.metric("📊 إشارات اليوم", len(st.session_state.signals_log) if 'signals_log' in st.session_state else 0)

st.divider()

# --- تهيئة session state ---
if 'last_signal_time' not in st.session_state:
    st.session_state.last_signal_time = {}
if 'signals_log' not in st.session_state:
    st.session_state.signals_log = []
if 'active_scans' not in st.session_state:
    st.session_state.active_scans = []
if 'last_scan_complete' not in st.session_state:
    st.session_state.last_scan_complete = time.time()

# --- أماكن العرض ---
status_placeholder = st.empty()
scan_progress = st.empty()
signal_placeholder = st.empty()
stats_placeholder = st.empty()

# --- حلقة الفحص السريع (كل 10-15 ثانية) ---
while True:
    try:
        scan_start = time.time()
        st.session_state.scan_count += 1
        
        # عرض عداد تنازلي
        scan_progress.info(f"🔄 **الفحص #{st.session_state.scan_count}** - جاري فحص {len(SYMBOLS)} زوج...")
        
        new_signals = []
        
        # فحص جميع الأزواج
        for i, symbol in enumerate(SYMBOLS):
            # تحديث التقدم
            if i % 5 == 0:  # كل 5 أزواج
                scan_progress.text(f"📊 التقدم: {i+1}/{len(SYMBOLS)} - جاري فحص {symbol}")
            
            # منع التكرار (كل 3 دقائق بدلاً من 5 للسرعة)
            now = time.time()
            if symbol in st.session_state.last_signal_time:
                if now - st.session_state.last_signal_time[symbol] < 180:  # 3 دقائق
                    continue
            
            try:
                # جلب البيانات
                if symbol == 'GOLD':
                    fsym, tsym = 'XAU', 'USD'
                elif len(symbol) == 6:
                    fsym, tsym = symbol[:3], symbol[3:]
                else:
                    fsym, tsym = symbol.replace("USD", ""), "USD"
                
                # بيانات سريعة (1 دقيقة و 5 دقائق فقط)
                url_1m = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit=50&api_key={API_KEY}"
                r1 = requests.get(url_1m, timeout=3).json()
                df_1m = pd.DataFrame(r1['Data']['Data'])
                
                url_5m = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit=50&aggregate=5&api_key={API_KEY}"
                r5 = requests.get(url_5m, timeout=3).json()
                df_5m = pd.DataFrame(r5['Data']['Data'])
                
                if df_1m.empty or df_5m.empty:
                    continue
                
                signal, confidence, price, volatility, rsi_value = get_signal_fast(df_1m, df_5m)
                
                if signal != "NEUTRAL" and confidence >= 80:
                    st.session_state.last_signal_time[symbol] = time.time()
                    entry_time = datetime.now()
                    
                    # حساب المدة الذكية
                    duration_str, duration_minutes = smart_timer.calculate_duration(
                        symbol, signal, volatility
                    )
                    
                    # رسالة التليجرام
                    emoji = "🟢" if signal == "BUY" else "🔴"
                    direction_ar = "صعود" if signal == "BUY" else "هبوط"
                    exit_time = entry_time + timedelta(minutes=duration_minutes)
                    
                    msg = f"""
🎯 **إشارة: {symbol}**

{emoji} **الاتجاه:** {direction_ar}
⏳ **مدة الصفقة:** {duration_str}
⏰ **وقت الدخول:** {entry_time.strftime('%H:%M:%S')}
⏱️ **وقت الخروج:** {exit_time.strftime('%H:%M:%S')}
💪 **الثقة:** {confidence}%
💰 **السعر:** {price:.4f}
📊 **التقلب:** {volatility:.2f}%

⚡ **فحص سريع | تحديث كل 10 ثوانٍ**
"""
                    
                    if bot:
                        try:
                            bot.send_message(CHAT_ID, msg)
                            new_signals.append(symbol)
                            
                            # تسجيل
                            st.session_state.signals_log.append({
                                'الوقت': entry_time.strftime('%H:%M:%S'),
                                'الزوج': symbol,
                                'الإشارة': direction_ar,
                                'المدة': duration_str,
                                'وقت الخروج': exit_time.strftime('%H:%M:%S'),
                                'الثقة': confidence,
                                'السعر': price
                            })
                        except:
                            pass
                            
            except Exception as e:
                continue
        
        # عرض الإشارات الجديدة
        if new_signals:
            with signal_placeholder.container():
                st.success(f"🎯 **تم العثور على {len(new_signals)} إشارة جديدة!**")
                for sym in new_signals:
                    st.write(f"• {sym}")
                st.balloons()
        
        # عرض الإحصائيات
        scan_duration = time.time() - scan_start
        stats_placeholder.info(f"""
        📊 **نتائج الفحص #{st.session_state.scan_count}**
        • ⏱️ زمن الفحص: {scan_duration:.1f} ثانية
        • 🎯 إشارات جديدة: {len(new_signals)}
        • ⏳ وقت التالي: 10-15 ثانية
        """)
        
        # عرض آخر 5 إشارات
        if st.session_state.signals_log:
            with st.expander("📋 سجل الإشارات (آخر 10)", expanded=False):
                df_log = pd.DataFrame(st.session_state.signals_log[-10:])
                st.dataframe(df_log, use_container_width=True)
        
        # تحديث حالة الفحص
        status_placeholder.success(f"✅ اكتمل الفحص #{st.session_state.scan_count} - وجد {len(new_signals)} إشارة - زمن: {scan_duration:.1f}ث")
        
        # انتظار 10-15 ثانية بين الفحوصات (سرعة قصوى مع تجنب حظر API)
        wait_time = 12  # 12 ثانية وسطياً
        for remaining in range(wait_time, 0, -1):
            status_placeholder.info(f"⏳ انتظار {remaining} ثانية حتى الفحص التالي...")
            time.sleep(1)
        
    except Exception as e:
        status_placeholder.error(f"❌ خطأ: {str(e)[:50]} - إعادة المحاولة بعد 5 ثوانٍ")
        time.sleep(5)
