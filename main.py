import logging
import sys
import os
import random
import threading
from datetime import datetime, timedelta
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

# Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Bot with Flask is Running!"

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
user_collection = db["users"]

# Social Media Links
TELEGRAM_CHANNEL_LINK = "https://t.me/YourChannel"
TWITTER_LINK = "https://twitter.com/YourTwitter"
YOUTUBE_LINK = "https://youtube.com/YourYouTube"

# Constants
WELCOME_IMAGE_PATH = "preview.jpg"
WELCOME_MESSAGE = (
    "👋 Welcome to Alien Enigma Bot!\n\n"
    "Earn points by joining the Daily Lucky Draw, Fighting Aliens and inviting frens.\n\n"
    "🔍 What are these points for?\n"
    "- Stay tuned to find out!\n"
    "Pro Tip: Fight Aliens to earn more points\n"
    "Click the button below to claim your daily points!"
)
REFERRAL_POINTS = 20  # Points awarded to the referrer

# Format time into 'Hh Mm' format
def format_time(seconds):
    remaining_time = timedelta(seconds=int(seconds))
    return f"{remaining_time.seconds // 3600}h {remaining_time.seconds % 3600 // 60}m"

# Start command
async def start(update: Update, context: CallbackContext):
    """Sends welcome message with an image, claim button, and social buttons."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")

    # Check if the user came from a referral link
    referred_by = None
    if context.args:
        referred_by = context.args[0]

    user_data = user_collection.find_one({"user_id": user_id})
    if not user_data:
        user_data = {"user_id": user_id, "points": 0, "last_claim": None, "referred_by": None}
        user_collection.insert_one(user_data)

    if referred_by and referred_by != str(user_id):
        referred_by = int(referred_by)
        referrer_data = user_collection.find_one({"user_id": referred_by})
        if referrer_data:
            user_collection.update_one(
                {"user_id": referred_by},
                {"$inc": {"points": REFERRAL_POINTS}}
            )
            user_collection.update_one(
                {"user_id": user_id},
                {"$set": {"referred_by": referred_by}}
            )

            logger.info(f"User {user_id} was referred by {referred_by}")
            await context.bot.send_message(
                chat_id=referred_by,
                text=f"🎉 You earned {REFERRAL_POINTS} points for referring {update.effective_user.first_name}! Your new balance is {referrer_data['points'] + REFERRAL_POINTS} points."
            )

    keyboard = [
        [InlineKeyboardButton("🎁 Claim Daily Points", callback_data="claim_points")],
        [
            InlineKeyboardButton("📢 Telegram", url=TELEGRAM_CHANNEL_LINK),
            InlineKeyboardButton("🐦 Twitter", url=TWITTER_LINK),
            InlineKeyboardButton("▶️ YouTube", url=YOUTUBE_LINK),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        with open(WELCOME_IMAGE_PATH, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption=WELCOME_MESSAGE, reply_markup=reply_markup)
    except FileNotFoundError:
        logger.error(f"Welcome image not found at {WELCOME_IMAGE_PATH}")
        await update.message.reply_text(WELCOME_MESSAGE, reply_markup=reply_markup)

# Claim points functionality
async def claim_points(update: Update, context: CallbackContext):
    """Handles daily point claims with a 24-hour cooldown."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    current_time = datetime.now()

    logger.info(f"User {user_id} clicked claim button")

    user_data = user_collection.find_one({"user_id": user_id})
    if not user_data:
        user_data = {"user_id": user_id, "points": 0, "last_claim": None, "referred_by": None}
        user_collection.insert_one(user_data)

    last_claim_time = user_data.get("last_claim", None)
    if last_claim_time:
        time_since_last_claim = (current_time - last_claim_time).total_seconds()
        if time_since_last_claim < 86400:
            remaining_time = 86400 - time_since_last_claim
            await query.message.reply_text(f"⏳ You've already claimed! Wait {format_time(remaining_time)}.")
            return

    points = random.randint(10, 100)
    user_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"points": points}, "$set": {"last_claim": current_time}}
    )

    updated_user_data = user_collection.find_one({"user_id": user_id})
    new_balance = updated_user_data.get("points", 0)

    await query.message.reply_text(f"🎉 You received {points} points! Your balance is now {new_balance}.")

# Referral system
async def referral(update: Update, context: CallbackContext):
    """Handles referral system button."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    referral_link = f"https://t.me/Realrushappbot?start={user_id}"
    await query.message.reply_text(f"🔗 Invite friends and earn rewards!\nShare this referral link: {referral_link}")

# Balance command
async def balance(update: Update, context: CallbackContext):
    """Sends the user's current point balance."""
    user_id = update.effective_user.id
    user_data = user_collection.find_one({"user_id": user_id})
    points = user_data.get("points", 0)
    await update.message.reply_text(f"💰 Your current balance is {points} points.")

# Error handler
async def error_handler(update: Update, context: CallbackContext):
    """Handles unexpected errors."""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ An error occurred. Please try again later.")

# Initialize Telegram bot
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("balance", balance))
application.add_handler(CallbackQueryHandler(claim_points, pattern="^claim_points$"))
application.add_handler(CallbackQueryHandler(referral, pattern="^referral$"))
application.add_error_handler(error_handler)

def run_flask():
    """Run Flask in a separate thread."""
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Run the Telegram bot in the main thread
    logger.info("Starting Telegram bot polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
