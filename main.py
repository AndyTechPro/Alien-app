import logging
import sys
import os
import signal
import random
from datetime import datetime, timedelta
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
MONGO_URI = os.getenv("MONGO_URI")  # Add Mongo URI to your .env file

# Social Media Links (Update These)
TELEGRAM_CHANNEL_LINK = "https://t.me/YourChannel"
TWITTER_LINK = "https://twitter.com/YourTwitter"
YOUTUBE_LINK = "https://youtube.com/YourYouTube"

# Message texts
WELCOME_MESSAGE = (
    "👋 Welcome to Alien Enigma Bot!\n\n"
    "Earn points by joining the Daily Lucky Draw, Fighting Aliens and inviting frens.\n\n"
    "🔍 What are these points for?\n"
    "- Stay tuned to find out!\n"
    "Pro Tip: Fight Aliens to earn more points\n"
    "Click the button below to claim your daily points!"
)

# Referral points
referral_points = 20  # Points awarded to the referrer

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
    """Sends welcome message with an image, claim button, and social buttons."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")

    # Check if the user came from a referral link
    referred_by = None
    if context.args:
        referred_by = context.args[0]  # Get the user ID of the referrer from the start parameter

    user_data = user_collection.find_one({"user_id": user_id})
    if not user_data:
        # Initialize user data with default values for new users
        user_data = {"user_id": user_id, "points": 0, "last_claim": None, "referred_by": None}
        user_collection.insert_one(user_data)  # Insert new user into MongoDB

    if referred_by and referred_by != str(user_id):
        referred_by = int(referred_by)  # Convert string to integer

        referrer_data = user_collection.find_one({"user_id": referred_by})
        if referrer_data:
            user_collection.update_one(
                {"user_id": referred_by},
                {"$inc": {"points": referral_points}},
            )
            user_collection.update_one(
                {"user_id": user_id},
                {"$set": {"referred_by": referred_by}},
            )

            logger.info(f"User {user_id} was referred by {referred_by}")
            logger.info(f"Referrer {referred_by} received {referral_points} points")

            # Notify the referrer
            try:
                await context.bot.send_message(
                    chat_id=referred_by,
                    text=f"🎉 You earned {referral_points} points for referring {update.effective_user.first_name}! Your new balance is {referrer_data['points'] + referral_points} points."
                )
            except Exception as e:
                logger.error(f"Failed to send referral message to {referred_by}: {e}")

    # Standard welcome message
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

    # Check if the user exists in the database
    user_data = user_collection.find_one({"user_id": user_id})

    if not user_data:
        # Initialize user data with default values for new users
        user_data = {"user_id": user_id, "points": 0, "last_claim": None, "referred_by": None}
        user_collection.insert_one(user_data)
        logger.info(f"Created new user in DB: {user_id}")

    last_claim_time = user_data.get("last_claim", None)

    if last_claim_time:
        time_since_last_claim = (current_time - last_claim_time).total_seconds()
        if time_since_last_claim < 86400:  # 24 hours
            remaining_time = 86400 - time_since_last_claim
            keyboard = [
                [InlineKeyboardButton("🎟 Refer & Earn", callback_data="referral")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                f"⏳ You've already claimed your daily points! Wait {format_time(remaining_time)} to claim again.",
                reply_markup=reply_markup)
            return

    # Points awarded to the current user
    points = random.randint(10, 100)

    # Update the user's points and last claim time in the database
    user_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"points": points}, "$set": {"last_claim": current_time}}
    )

    # Fetch the updated user data
    updated_user_data = user_collection.find_one({"user_id": user_id})
    new_balance = updated_user_data.get("points", 0)

    keyboard = [
        [InlineKeyboardButton("🎟 Refer & Earn", callback_data="referral")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(f"🎉 You received {points} daily points! Your balance is now {new_balance} points.",
                                   reply_markup=reply_markup)
    logger.info(f"User {user_id} received {points} points. New balance: {new_balance}")


# Referral system
async def referral(update: Update, context: CallbackContext):
    """Handles referral system button."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    referral_link = f"https://t.me/Realrushappbot?start={user_id}"

    await query.message.reply_text(f"🔗 Invite your friends and earn rewards!\nShare this referral link: {referral_link}")
    logger.info(f"User {user_id} checked referral system.")


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


# Signal handler to shutdown bot
def signal_handler(signum, frame):
    """Handles bot shutdown signal."""
    logger.info("Signal received, shutting down...")
    exit(0)


# Main bot function
def main():
    """Main bot function."""
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))

    # Add button handlers
    application.add_handler(CallbackQueryHandler(claim_points, pattern="^claim_points$"))
    application.add_handler(CallbackQueryHandler(referral, pattern="^referral$"))

    # Add error handler
    application.add_error_handler(error_handler)

    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


# Run the bot
if __name__ == "__main__":
    main()
