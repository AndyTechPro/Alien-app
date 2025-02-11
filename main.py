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
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Set your deployed domain

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
    "\U0001F44B Welcome to Alien Enigma Bot!\n\n"
    "Earn points by joining the Daily Lucky Draw, Fighting Aliens and inviting friends.\n\n"
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
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")

    referred_by = context.args[0] if context.args else None

    user_data = user_collection.find_one({"user_id": user_id})
    if not user_data:
        user_collection.insert_one({"user_id": user_id, "points": 0, "last_claim": None, "referred_by": None})

    if referred_by and referred_by != str(user_id):
        referred_by = int(referred_by)
        referrer_data = user_collection.find_one({"user_id": referred_by})
        if referrer_data:
            user_collection.update_one({"user_id": referred_by}, {"$inc": {"points": REFERRAL_POINTS}})
            user_collection.update_one({"user_id": user_id}, {"$set": {"referred_by": referred_by}})

            await context.bot.send_message(
                chat_id=referred_by,
                text=f"🎉 You earned {REFERRAL_POINTS} points for referring {update.effective_user.first_name}!"
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

    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=reply_markup)


# Claim points function
async def claim_points(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    current_time = datetime.now()

    user_data = user_collection.find_one({"user_id": user_id})
    last_claim_time = user_data.get("last_claim")

    if last_claim_time and (current_time - last_claim_time).total_seconds() < 86400:
        await query.message.reply_text(
            f"⏳ You've already claimed! Wait {format_time(86400 - (current_time - last_claim_time).total_seconds())}.")
        return

    points = random.randint(10, 100)
    user_collection.update_one({"user_id": user_id}, {"$inc": {"points": points}, "$set": {"last_claim": current_time}})
    await query.message.reply_text(
        f"🎉 You received {points} points! Your balance is now {user_data['points'] + points}.")


# Balance command
async def balance(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_data = user_collection.find_one({"user_id": user_id})
    points = user_data.get("points", 0)
    await update.message.reply_text(f"💰 Your current balance is {points} points.")


# Telegram Webhook
async def set_webhook():
    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/telegram")


@app.route("/telegram", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(), application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200


# Initialize Telegram bot
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("balance", balance))
application.add_handler(CallbackQueryHandler(claim_points, pattern="^claim_points$"))


async def startup():
    await set_webhook()


asyncio.run(startup())

# Run Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
