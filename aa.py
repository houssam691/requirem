import pandas as pd
import pandas_ta as ta
import telebot
import time
import requests
from datetime import datetime

# --- إعدادات المستخدم ---
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
bot = telebot.TeleBot(TOKEN)

SYMBOLS = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF', 'BTCUSD', 'ETHUSD']

# ذاكرة مانع التكرار
last_signals = {}

def get_live_data(symbol):
    try:
        # تقليل عدد الشموع المطلوبة لتخفيف الجهد على المعالج
        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={symbol[:3]}&tsym={symbol[3:]}&limit=60"
        response = requests.get(url, timeout=15)
        data = response.json()
        if data['Response'] == 'Success':
            df = pd.DataFrame(data['Data']['Data'])
            df['close'] = df['close'].astype(float)
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def check_market(symbol):
    try:
        current_time = time.time()
        
        # التخطي الكامل للزوج (Skip)
        if symbol in last_signals:
            if current_time - last_signals[symbol] < 60:
                return 

        df = get_live_data(symbol)
        if df.empty or len(df) < 20:
            return

        df['RSI'] = ta.rsi(df['close'], length=14)
        df['EMA'] = ta.ema(df['close'], length=50)
        last = df.iloc[-1]

        if last['close'] > last['EMA'] and last['RSI'] < 50:
            bot.send_message(CHAT_ID, f"🟢 **CALL (صعود)**\nالزوج: {symbol}\nالسعر: {last['close']}")
            last_signals[symbol] = current_time 
            
        elif last['close'] < last['EMA'] and last['RSI'] > 65:
            bot.send_message(CHAT_ID, f"🔴 **PUT (هبوط)**\nالزوج: {symbol}\nالسعر: {last['close']}")
            last_signals[symbol] = current_time 

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # رسالة التشغيل تظهر في تليجرام
    try:
        bot.send_message(CHAT_ID, "🚀 البوت يعمل الآن ويراقب السوق...")
    except: pass
        
    print("🚀 تم الانتقال للمصدر البديل. البحث المستمر يعمل الآن...")

    while True:
        try:
            for pair in SYMBOLS:
                check_market(pair)
                # زيادة وقت الانتظار قليلاً (1 ثانية) لخفض استهلاك المعالج CPU
                # هذا سيمنع دخولك في الـ Tarpit ويمنع انهيار السكربت
                time.sleep(1) 

            print(f"🔄 دورة فحص مكتملة [{datetime.now().strftime('%H:%M:%S')}]")

        except Exception as e:
            time.sleep(10)
            continue
