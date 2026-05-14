import streamlit as st
import yfinance as yf
import pandas_ta as ta
import telebot
import time
from datetime import datetime

# --- الإعدادات (ضع توكن البوت الخاص بك هنا) ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
bot = telebot.TeleBot(TOKEN)

# قائمة العملات (Forex)
SYMBOLS = [
    'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 
    'USDCAD=X', 'USDCHF=X', 'NZDUSD=X', 'EURGBP=X'
]

# واجهة Streamlit بسيطة لضمان بقاء السبيس نشطاً
st.title("🤖 بوت قناص الفوركس الذكي")
st.write("البوت يعمل الآن في الخلفية ويراقب الأسواق...")
status_text = st.empty()

def check_market():
    for symbol in SYMBOLS:
        try:
            # جلب البيانات
            data = yf.download(symbol, interval="5m", period="1d", progress=False)
            if len(data) < 200: continue

            # حساب المؤشرات
            data['EMA200'] = ta.ema(data['Close'], length=200)
            data['RSI'] = ta.rsi(data['Close'], length=14)
            macd = ta.macd(data['Close'])
            data['MACD'] = macd['MACD_12_26_9']
            data['Signal'] = macd['MACDs_12_26_9']

            last = data.iloc[-1]
            prev = data.iloc[-2]
            clean_name = symbol.replace('=X', '')

            # استراتيجية القنص:
            # شراء: سعر فوق EMA200 + RSI تحت 40 + تقاطع MACD إيجابي
            if last['Close'] > last['EMA200']:
                if last['RSI'] < 40 and last['MACD'] > last['Signal'] and prev['MACD'] <= prev['Signal']:
                    bot.send_message(CHAT_ID, f"🟢 إشارة شراء قوية: {clean_name}\nالسعر: {last['Close']:.5f}\nالسبب: تقاطع MACD فوق EMA200")

            # بيع: سعر تحت EMA200 + RSI فوق 60 + تقاطع MACD سلبي
            elif last['Close'] < last['EMA200']:
                if last['RSI'] > 60 and last['MACD'] < last['Signal'] and prev['MACD'] >= prev['Signal']:
                    bot.send_message(CHAT_ID, f"🔴 إشارة بيع قوية: {clean_name}\nالسعر: {last['Close']:.5f}\nالسبب: تقاطع MACD تحت EMA200")

        except Exception as e:
            print(f"Error checking {symbol}: {e}")

# حلقة التشغيل الدائمة
if __name__ == "__main__":
    last_pulse = 0
    while True:
        check_market()
        
        # إرسال نبض البوت كل ساعة (Heartbeat)
        if time.time() - last_pulse >= 3600:
            current_time = datetime.now().strftime("%H:%M")
            bot.send_message(CHAT_ID, f"✅ نبض البوت: مراقبة {len(SYMBOLS)} أزواج مستمرة.\nالوقت: {current_time}")
            last_pulse = time.time()
        
        status_text.text(f"آخر فحص للسوق: {datetime.now().strftime('%H:%M:%S')}")
        time.sleep(300)  # فحص كل 5 دقائق
