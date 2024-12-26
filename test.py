import pandas as pd
import yfinance as yf
import requests
import telebot

BOT_TOKEN = '7083581490:AAE3gLoSvPxIkRwTW9YCjhOEHznbBTL2NBc'

EXCEL_URL = "https://raw.githubusercontent.com/username/repo/main/stock_list.xlsx"

bot = telebot.TeleBot(BOT_TOKEN)

# Function to fetch current stock prices
def fetch_current_prices(symbols):
    prices = {}
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            price = ticker.history(period="1d")["Close"].iloc[-1]
            prices[symbol] = round(price, 2)
        except Exception as e:
            prices[symbol] = f"Error: {e}"
    return prices

@bot.message_handler(commands=["getprices"])
def get_prices(message):
    try:
        # Download the Excel file from GitHub
        response = requests.get(EXCEL_URL)
        response.raise_for_status()  # Raise error for failed request
        
        # Save the Excel file locally
        with open("temp_stock_list.xlsx", "wb") as file:
            file.write(response.content)
        
        # Read the Excel file into a DataFrame
        df = pd.read_excel("temp_stock_list.xlsx")
        
        # Ensure the file contains a 'Symbol' column
        if "Symbol" not in df.columns:
            bot.reply_to(message, "The Excel file must contain a 'Symbol' column.")
            return
        
        # Extract stock symbols and fetch current prices
        symbols = df["Symbol"].dropna().tolist()
        prices = fetch_current_prices(symbols)
        
        # Format the response
        response_message = "📊 *Current Stock Prices* 📊\n"
        for symbol, price in prices.items():
            response_message += f"{symbol}: {price}\n"
        
        # Send the response to the user
        bot.reply_to(message, response_message, parse_mode="Markdown")
    
    except Exception as e:
        bot.reply_to(message, f"An error occurred: {e}")

# Function to handle the /start command
@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message, "Welcome to the Stock Price Bot! Use /getprices to fetch current stock prices.")

# Start polling
bot.polling()