import logging
import sys
import os
import random
import asyncio
import threading
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from dotenv import load_dotenv
from pymongo import MongoClient
import nest_asyncio

nest_asyncio.apply()

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
    return "Telegram Bot with Flask is Running!".encode("utf-8")


# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
user_collection = db["users"]

# Constants
REFERRAL_POINTS = 20  # Points awarded to the referrer
WELCOME_IMAGE_PATH = "preview.jpg"  # Ensure this file exists in your project folder
WELCOME_IMAGE_URL = "https://example.com/your-image.jpg"  # Alternative (use direct image URL if needed)
WELCOME_MESSAGE = (
    "👋 Welcome to Alien Enigma Bot!\n\n"
    "Earn points by joining the Daily Lucky Draw, Fighting Aliens, and inviting friends.\n\n"
    "🔍 What are these points for?\n"
    "- Stay tuned to find out!\n"
    "🚀 Pro Tip: Fight Aliens to earn more points\n"
    "Click the button below to claim your daily points!"
)


# Format time into 'Hh Mm' format
def format_time(seconds):
    remaining_time = timedelta(seconds=int(seconds))
    return f"{remaining_time.seconds // 3600}h {remaining_time.seconds % 3600 // 60}m"


# Start command
async def start(update: Update, context):
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

    keyboard = [[InlineKeyboardButton("🎁 Claim Daily Points", callback_data="claim_points")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await update.message.reply_photo(
            photo=open(WELCOME_IMAGE_PATH, 'rb'),
            caption=WELCOME_MESSAGE,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.warning(f"Failed to send local image, falling back to URL: {e}")
        await update.message.reply_photo(
            photo=WELCOME_IMAGE_URL,
            caption=WELCOME_MESSAGE,
            reply_markup=reply_markup
        )


# Claim points function
async def claim_points(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    current_time = datetime.now()

    user_data = user_collection.find_one({"user_id": user_id})
    last_claim_time = user_data.get("last_claim")

    if last_claim_time and (current_time - last_claim_time).total_seconds() < 86400:
        await query.message.reply_text(
            f"⏳ You've already claimed! Wait {format_time(86400 - (current_time - last_claim_time).total_seconds())}."
        )
        return

    points = random.randint(10, 100)
    user_collection.update_one({"user_id": user_id}, {"$inc": {"points": points}, "$set": {"last_claim": current_time}})
    new_balance = user_data.get("points", 0) + points
    await query.message.reply_text(f"🎉 You received {points} points! Your balance is now {new_balance}.")


# Balance command
async def balance(update: Update, context):
    user_id = update.effective_user.id
    user_data = user_collection.find_one({"user_id": user_id})
    points = user_data.get("points", 0)
    await update.message.reply_text(f"💰 Your current balance is {points} points.")


# Initialize Telegram bot
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("balance", balance))
application.add_handler(CallbackQueryHandler(claim_points, pattern="^claim_points$"))


# Run Flask in a separate thread
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


# Run Telegram bot using existing event loop
async def run_telegram():
    logging.info("📡 Starting Telegram bot in polling mode...")
    await application.run_polling()


# Start both Flask and Telegram bot
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(run_telegram())
