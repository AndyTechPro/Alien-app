import logging
import sys
import os
import signal
import threading
import asyncio
from flask import Flask
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
from pymongo import MongoClient

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
user_collection = db["users"]

# Flask App Setup
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

# Start command
async def start(update: Update, context: CallbackContext):
    """Handles the /start command"""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")
    await update.message.reply_text("Hello! I am your bot.")

# Claim points command (dummy function for now)
async def claim_points(update: Update, context: CallbackContext):
    """Handles claim points button click"""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("You claimed your daily points!")

# Referral command (dummy function for now)
async def referral(update: Update, context: CallbackContext):
    """Handles referral system button"""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Share your referral link!")

# Balance command
async def balance(update: Update, context: CallbackContext):
    """Sends the user's current point balance"""
    user_id = update.effective_user.id
    user_data = user_collection.find_one({"user_id": user_id})
    points = user_data.get("points", 0) if user_data else 0
    await update.message.reply_text(f"💰 Your current balance is {points} points.")

# Error handler
async def error_handler(update: Update, context: CallbackContext):
    """Handles unexpected errors"""
    logger.error(f"Update {update} caused error {context.error}")

# Signal handler to shutdown bot
def signal_handler(signum, frame):
    """Handles bot shutdown signal"""
    logger.info("Signal received, shutting down...")
    exit(0)

# Create bot application
application = Application.builder().token(TOKEN).build()

# Add command handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("balance", balance))
application.add_handler(CallbackQueryHandler(claim_points, pattern="^claim_points$"))
application.add_handler(CallbackQueryHandler(referral, pattern="^referral$"))

# Add error handler
application.add_error_handler(error_handler)

# Function to run bot
def run_bot():
    """Run the bot using asyncio properly."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.run_polling(allowed_updates=Update.ALL_TYPES))

# Run bot in a separate thread
threading.Thread(target=run_bot, daemon=True).start()

# Run Flask server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
