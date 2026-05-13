import pandas as pd
import telebot
import time
import requests
from datetime import datetime

# إعدادات البوت
TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
bot = telebot.TeleBot(TOKEN, threaded=False)

SYMBOLS = [
    'BTCUSD', 'ETHUSD', 'BNBUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD',
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'GOLD'
]

last_signal_time = {symbol: 0 for symbol in SYMBOLS}
COOLDOWN_SECONDS = 300 
last_heartbeat_hour = -1 # لمتابعة إرسال رسالة "أنا شغال" كل ساعة

def calculate_rsi(series, period=14):
    try:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    except:
        return pd.Series([50] * len(series))

def check_market(symbol):
    global last_signal_time
    try:
        current_time = time.time()
        if current_time - last_signal_time[symbol] < COOLDOWN_SECONDS:
            return

        fsym = symbol[:-3] if any(x in symbol for x in ['USD', 'JPY', 'CAD']) else symbol[:3]
        tsym = symbol[-3:]
        if symbol == 'GOLD': fsym, tsym = 'XAU', 'USD'

        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit=50"
        response = requests.get(url, timeout=15).json()
        
        if 'Data' not in response or 'Data' not in response['Data'] or not response['Data']['Data']:
            return
            
        df = pd.DataFrame(response['Data']['Data'])
        if len(df) < 30: return
        
        df['EMA'] = df['close'].ewm(span=50, adjust=False).mean()
        df['RSI'] = calculate_rsi(df['close'])
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        signal_sent = False
        if last['close'] > last['EMA'] and prev['RSI'] < 30 and last['RSI'] >= 30:
            bot.send_message(CHAT_ID, f"🎯 فرصة صعود: {symbol}\n📈 RSI: {round(last['RSI'], 2)}")
            signal_sent = True
        elif last['close'] < last['EMA'] and prev['RSI'] > 70 and last['RSI'] <= 70:
            bot.send_message(CHAT_ID, f"🎯 فرصة هبوط: {symbol}\n📉 RSI: {round(last['RSI'], 2)}")
            signal_sent = True
            
        if signal_sent:
            last_signal_time[symbol] = current_time
            
    except Exception as e:
        print(f"⚠️ خطأ في {symbol}: {e}")

if __name__ == "__main__":
    print("🚀 البوت بدأ العمل...")
    try:
        bot.send_message(CHAT_ID, "🛡️ البوت متصل الآن بنظام التقرير الساعي.")
    except:
        pass
    
    while True:
        # ميزة رسالة "أنا شغال" كل ساعة
        current_hour = datetime.now().hour
        if current_hour != last_heartbeat_hour:
            try:
                bot.send_message(CHAT_ID, f"✅ نبض البوت: أنا أعمل حالياً وأراقب {len(SYMBOLS)} زوجاً.\n⏰ الوقت: {datetime.now().strftime('%H:%M')}")
                last_heartbeat_hour = current_hour
            except:
                pass

        for s in SYMBOLS:
            check_market(s)
            time.sleep(1)
