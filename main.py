import logging
import sys
import os
import random
import asyncio
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
from dotenv import load_dotenv
from pymongo import MongoClient

# Initialize Flask app
app = Flask(__name__)

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

# Social Media Links
TELEGRAM_CHANNEL_LINK = "https://t.me/YourChannel"
TWITTER_LINK = "https://twitter.com/YourTwitter"
YOUTUBE_LINK = "https://youtube.com/YourYouTube"

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
user_collection = db["users"]

# Format time
def format_time(seconds):
    remaining_time = timedelta(seconds=int(seconds))
    return f"{remaining_time.seconds // 3600}h {remaining_time.seconds % 3600 // 60}m"

# Start command
async def start(update: Update, context: CallbackContext):
    """Sends welcome message with buttons."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")

    keyboard = [
        [InlineKeyboardButton("🎁 Claim Daily Points", callback_data="claim_points")],
        [
            InlineKeyboardButton("📢 Telegram", url=TELEGRAM_CHANNEL_LINK),
            InlineKeyboardButton("🐦 Twitter", url=TWITTER_LINK),
            InlineKeyboardButton("▶️ YouTube", url=YOUTUBE_LINK),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("👋 Welcome! Click below to claim daily points.", reply_markup=reply_markup)

# Claim points function
async def claim_points(update: Update, context: CallbackContext):
    """Handles daily point claims."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    current_time = datetime.now()

    user_data = user_collection.find_one({"user_id": user_id}) or {"user_id": user_id, "points": 0, "last_claim": None}
    last_claim_time = user_data.get("last_claim")

    if last_claim_time and (current_time - last_claim_time).total_seconds() < 86400:
        remaining_time = 86400 - (current_time - last_claim_time).total_seconds()
        await query.message.reply_text(f"⏳ Wait {format_time(remaining_time)} to claim again.")
        return

    points = random.randint(10, 100)
    user_collection.update_one({"user_id": user_id}, {"$inc": {"points": points}, "$set": {"last_claim": current_time}}, upsert=True)
    await query.message.reply_text(f"🎉 You received {points} points!")

# Balance command
async def balance(update: Update, context: CallbackContext):
    """Shows user's point balance."""
    user_id = update.effective_user.id
    user_data = user_collection.find_one({"user_id": user_id}) or {"points": 0}
    await update.message.reply_text(f"💰 Your balance: {user_data['points']} points.")

# Error handler
async def error_handler(update: Update, context: CallbackContext):
    """Handles errors."""
    logger.error(f"Update {update} caused error {context.error}")
    await update.message.reply_text("⚠️ An error occurred. Please try again.")

# Flask route (keeps deployment alive)
@app.route('/')
def home():
    return "Alien Enigma Bot is running! 🚀"

# Start the bot inside an asyncio loop
async def run_bot():
    """Runs the Telegram bot."""
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CallbackQueryHandler(claim_points, pattern="^claim_points$"))
    application.add_error_handler(error_handler)

    logger.info("Starting bot polling...")
    await application.run_polling()

# Run bot in the background
async def start_async():
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())

if __name__ == "__main__":
    asyncio.run(start_async())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
