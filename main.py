import pandas as pd
import ta  # المكتبة الجديدة الخفيفة
import telebot
import time
import requests
from datetime import datetime

TOKEN = '8773849578:AAH9a6-8hU5YFYTad2EA5jQyfffIoeL8npk'
CHAT_ID = '7553333305'
bot = telebot.TeleBot(TOKEN)

SYMBOLS = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF', 'BTCUSD', 'ETHUSD']
last_signals = {}

def get_live_data(symbol):
    try:
        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={symbol[:3]}&tsym={symbol[3:]}&limit=100"
        response = requests.get(url, timeout=15)
        data = response.json()
        if data['Response'] == 'Success':
            df = pd.DataFrame(data['Data']['Data'])
            df['close'] = df['close'].astype(float)
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

def check_market(symbol):
    try:
        current_time = time.time()
        if symbol in last_signals and (current_time - last_signals[symbol] < 60):
            return 

        df = get_live_data(symbol)
        if df.empty or len(df) < 50: return

        # --- الحساب باستخدام المكتبة الجديدة الخفيفة ---
        df['RSI'] = ta.momentum.rsi(df['close'], window=14)
        df['EMA'] = ta.trend.ema_indicator(df['close'], window=50)
        
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
    print("🚀 البدء باستخدام المكتبة الخفيفة لضمان الاستقرار...")
    while True:
        try:
            for pair in SYMBOLS:
                check_market(pair)
                time.sleep(1)
        except Exception as e:
            time.sleep(10)
            continue
