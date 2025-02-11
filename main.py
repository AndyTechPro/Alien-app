import logging
import sys
import os
import signal
import random
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
from dotenv import load_dotenv
from pymongo import MongoClient

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Constants
WELCOME_IMAGE_PATH = "preview.jpg"

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# Social Media Links
TELEGRAM_CHANNEL_LINK = "https://t.me/YourChannel"
TWITTER_LINK = "https://twitter.com/YourTwitter"
YOUTUBE_LINK = "https://youtube.com/YourYouTube"

# Referral points
referral_points = 20

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
user_collection = db["users"]

# Format time into 'Hh Mm' format
def format_time(seconds):
    remaining_time = timedelta(seconds=int(seconds))
    return f"{remaining_time.seconds // 3600}h {remaining_time.seconds % 3600 // 60}m"

# Start command
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")

    keyboard = [[InlineKeyboardButton("🎁 Claim Daily Points", callback_data="claim_points")],
                [InlineKeyboardButton("📢 Telegram", url=TELEGRAM_CHANNEL_LINK),
                 InlineKeyboardButton("🐦 Twitter", url=TWITTER_LINK),
                 InlineKeyboardButton("▶️ YouTube", url=YOUTUBE_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        with open(WELCOME_IMAGE_PATH, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption="Welcome!", reply_markup=reply_markup)
    except FileNotFoundError:
        logger.error(f"Welcome image not found at {WELCOME_IMAGE_PATH}")
        await update.message.reply_text("Welcome!", reply_markup=reply_markup)

# Claim points
async def claim_points(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    current_time = datetime.now()

    user_data = user_collection.find_one({"user_id": user_id})
    if not user_data:
        user_data = {"user_id": user_id, "points": 0, "last_claim": None}
        user_collection.insert_one(user_data)

    last_claim_time = user_data.get("last_claim", None)
    if last_claim_time and (current_time - last_claim_time).total_seconds() < 86400:
        await query.message.reply_text("⏳ Please wait before claiming again.")
        return

    points = random.randint(10, 100)
    user_collection.update_one({"user_id": user_id}, {"$inc": {"points": points}, "$set": {"last_claim": current_time}})

    await query.message.reply_text(f"🎉 You received {points} points!")

# Referral system
async def referral(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    referral_link = f"https://t.me/Realrushappbot?start={user_id}"
    await query.message.reply_text(f"🔗 Invite friends: {referral_link}")

# Balance command
async def balance(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_data = user_collection.find_one({"user_id": user_id})
    points = user_data.get("points", 0)
    await update.message.reply_text(f"💰 Your balance: {points} points.")

# Error handler
async def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ An error occurred. Please try again later.")

# Flask server setup
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# Signal handler
def signal_handler(signum, frame):
    logger.info("Signal received, shutting down...")
    exit(0)

# Main function
def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CallbackQueryHandler(claim_points, pattern="^claim_points$"))
    application.add_handler(CallbackQueryHandler(referral, pattern="^referral$"))
    application.add_error_handler(error_handler)
    signal.signal(signal.SIGINT, signal_handler)

    bot_thread = Thread(target=application.run_polling, kwargs={"allowed_updates": Update.ALL_TYPES})
    bot_thread.start()
    run_flask()

if __name__ == "__main__":
    main()
