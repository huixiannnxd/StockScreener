import pandas as pd
import yfinance as yf
import requests
import telebot
from io import BytesIO
from datetime import datetime
import logging
import ta

BOT_TOKEN = '7083581490:AAE3gLoSvPxIkRwTW9YCjhOEHznbBTL2NBc'

EXCEL_URL = "https://raw.githubusercontent.com/huixiannnxd/StockScreener/main/bullish_stocks.xlsx"

bot = telebot.TeleBot(BOT_TOKEN)

# Function to fetch current stock prices
def check_condition(stock_data):
    for i in range(1, 5):
        if stock_data['Close'].iloc[-i-1] < stock_data['Low'].iloc[-i-2]:
            return True, stock_data['Low'].iloc[-i-2], stock_data.index[-i-1]
        return False, None, None


def get_current_price(symbol):
    try:
        # Fetch the last 5-minute interval data
        data = yf.download(tickers=symbol, period='1d', interval='5m')
        
        # Check if data is available
        if data.empty:
            print(f"No price data found for {symbol}.")
            return None
        
        # Get the latest closing price
        current_price = data['Close'].iloc[-1]
        return current_price
    
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return None

def check_signal(symbol, trigger_price):
   current_price = get_current_price(symbol)
   if isinstance(current_price, str) or trigger_price == None or current_price == None:
       return False
   else:
       if current_price >= trigger_price:
            return True
       else:
            return False
       
def get_atr(symbol, period='1mo', interval='1d', window=14):
    try:
        stock_data = yf.download(symbol, period=period, interval=interval)
        if len(stock_data) < window:
            logging.warning(f"Not enough data for ATR calculation for {symbol}")
            return None
        atr = ta.volatility.AverageTrueRange(
            high=stock_data['High'],
            low=stock_data['Low'],
            close=stock_data['Close'],
            window=window
        ).average_true_range()
        return atr.iloc[-1] if not atr.empty else None
    except Exception as e:
        logging.error(f"Error calculating ATR for {symbol}: {e}")
        return None
    
    # Define function for TPSL
def calculate_stop_loss_take_profit(row):
    to_enter = bool(row.get('To Enter', False))
    condition_met = bool(row.get('Condition Met', False))
    if pd.notnull(row['ATR']) and to_enter and condition_met:
        row['Stop Loss'] = row['Entry Price'] - 1.5 * row['ATR']
        row['Take Profit Price'] = row['Entry Price'] + 1.5 * row['ATR']
    else:
        row['Stop Loss'] = None
        row['Take Profit Price'] = None
    return row
       
@bot.message_handler(commands=['getprices'])
def handle_get_prices(message):
    
    try:
        bot.reply_to(message, "Fetching the Excel file from GitHub...")

        # Download the Excel file from GitHub
        response = requests.get(EXCEL_URL)
        response.raise_for_status()
        file_content = BytesIO(response.content)

        # Read the Excel file into a DataFrame
        stocks = pd.read_excel(file_content, engine='openpyxl')
        print(stocks.head())

        #Get current date
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Filter for list of stocks that is within the valid period
        valid_stocks = stocks[
        (stocks['Start on Open'] <= current_date) &
        (stocks['End on Close'] > current_date)].copy()

        valid_stocks_list = valid_stocks['Symbol'].tolist()


        # Check for condition
        results, entry_prices, trigger_dates = {}, {}, {}
        for stock in valid_stocks_list:
            try:
                stock_data = yf.download(stock, period='1mo')
                if len(stock_data) >= 5:
                    condition_met, entry_price, trigger_date = check_condition(stock_data)
                    results[stock] = condition_met
                    entry_prices[stock] = entry_price
                    trigger_dates[stock] = trigger_date
            except Exception as e:
                logging.error(f"Error processing {stock}: {e}")
        
        valid_stocks['Condition Met'] = valid_stocks['Symbol'].apply(lambda x: results.get(x, False))
        valid_stocks['Entry Price'] = valid_stocks['Symbol'].apply(lambda x: entry_prices.get(x))
        valid_stocks['Trigger Date'] = valid_stocks['Symbol'].apply(
            lambda x: trigger_dates.get(x).strftime('%Y-%m-%d') if pd.notnull(trigger_dates.get(x)) else None
        )
        
        # Filter active stocks
        active_stocks = valid_stocks[
        (pd.notnull(valid_stocks['Trigger Date']) &
        (valid_stocks['Trigger Date'] >= valid_stocks['Start on Open']) &
        (valid_stocks['Trigger Date'] < current_date) &
        (valid_stocks['Condition Met'])]

        active_stock_list = active_stocks['Symbol'].tolist()
        
        # Check for signals
        signals = {stock: check_signal(stock, active_stocks.loc[active_stocks['Symbol'] == stock, 'Entry Price'].iloc[0])
               for stock in active_stock_list}
        active_stocks['To Enter'] = active_stocks['Symbol'].apply(lambda x: signals.get(x, False) if x in active_stock_list else None)

        # Add ATR
        active_stocks['ATR'] = active_stocks['Symbol'].apply(lambda x: get_atr(x) if x in active_stock_list else None)
    
        # Add TPSL
        active_stocks['Stop Loss'] = None
        active_stocks['Take Profit Price'] = None
        active_stocks = active_stocks.apply(calculate_stop_loss_take_profit, axis=1)

        filtered_stocks = active_stocks[active_stocks['To Enter'] == True][['Symbol', 'Entry Price', 'Trigger Date', 'Stop Loss', 'Take Profit Price']]
        message_text = filtered_stocks.to_string(index=False)
        bot.reply_to(message, message_text)
        
    except requests.exceptions.RequestException as e:
        bot.reply_to(message, f"Error fetching the Excel file from GitHub: {e}")
    except Exception as e:
        bot.reply_to(message, f"An error occurred: {e}")

# Start the bot
print("Bot is running...")
bot.polling()
