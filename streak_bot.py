from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ParseMode
from dotenv import load_dotenv
from pytz import timezone
import os
import logging
import streak_database as db
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import requests
import random

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_GROUP_ID = int(os.getenv('TELEGRAM_GROUP_ID'))
ALLOWED_GROUP_ID = TELEGRAM_GROUP_ID

updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

def is_group_allowed(update):
    return update.effective_chat.id == ALLOWED_GROUP_ID

def restrict_group(func):
    def wrapper(update, context, *args, **kwargs):
        if not is_group_allowed(update):
            update.message.reply_text("You are not authorized to use this bot here.")
            return
        return func(update, context, *args, **kwargs)
    return wrapper

def fetch_motivational_quote():
    try:
        response = requests.get('https://api.quotable.io/random?tags=motivational')
        if response.status_code == 200:
            quote = response.json()
            return quote['content']
        else:
            return "Stay strong, stay focused!"
    except Exception:
        return "Stay strong, stay focused!"

'''
Starting from the below comment, bot handlers are present until the next section of the code.
'''

@restrict_group
def register(update, context):
    username = update.effective_user.username
    group_id = update.effective_chat.id
    try:
        goals = list(map(int, context.args))
        if len(goals) != 7:
            update.message.reply_text("Please provide 7 numbers for Monday to Sunday goals.")
            return
        db.register_user(username, group_id, goals)
        update.message.reply_text("Registered your goals successfully!")
    except:
        update.message.reply_text("Please use the format: /register 1 2 3 4 5 6 7")

@restrict_group
def modify(update, context):
    username = update.effective_user.username
    group_id = update.effective_chat.id
    try:
        goals = list(map(int, context.args))
        if len(goals) != 7:
            update.message.reply_text("Please provide 7 numbers for Monday to Sunday goals.")
            return
        db.modify_user_goals(username, group_id, goals)
        update.message.reply_text("Your goals have been updated successfully!")
    except:
        update.message.reply_text("Please use the format: /modify 1 2 3 4 5 6 7")

@restrict_group
def task_logger(update, context):
    if update.message.text.strip() == '+1':
        username = update.effective_user.username
        group_id = update.effective_chat.id

        if db.user_exists(username, group_id):
            db.increment_today_tasks(username, group_id)
            update.message.reply_text(f"Task logged! Keep going, @{username}!")
        else:
            update.message.reply_text("You need to register your goals first using /register.")

@restrict_group
def optout(update, context):
    username = update.effective_user.username
    group_id = update.effective_chat.id
    try:
        days = int(context.args[0])
        db.apply_opt_out(username, group_id, days)
        update.message.reply_text(f"Opted out for {days} day(s). We will miss you, get back soon!!")
    except:
        update.message.reply_text("Please use the format: /optout <number_of_days>")

@restrict_group
def optin(update, context):
    username = update.effective_user.username
    group_id = update.effective_chat.id

    db.apply_opt_in(username, group_id)
    update.message.reply_text("Hurrayy!!! You are now back in tracking!")

@restrict_group
def help_command(update, context):
    help_text = """
Available Commands:
/register 1 2 3 4 5 6 7 - Register your weekly goals.
/modify 1 2 3 4 5 6 7 - Modify your weekly goals.
/optout <days> - Opt-out for specified days.
/optin - Return to tracking.
/help - Show this help message.

Just send '+1' to log your task!
"""
    update.message.reply_text(help_text)

dispatcher.add_handler(CommandHandler('register', register))
dispatcher.add_handler(CommandHandler('modify', modify))
dispatcher.add_handler(CommandHandler('optout', optout))
dispatcher.add_handler(CommandHandler('optin', optin))
dispatcher.add_handler(CommandHandler('help', help_command))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), task_logger))


def morning_reminder(context):
    group_id = context.job.context

    # Fetch daily goals
    user_goals = db.get_all_user_goals(group_id)
    # Fetch punishments
    punished_users = db.get_users_with_punishment(group_id)
    # Fetch motivational quote
    quote = fetch_motivational_quote()

    # Build goals message
    goal_messages = "\n".join([f"@{username}: {goal} tasks today" for username, goal in user_goals])

    # Build punishment message
    punishment_messages = ""
    if punished_users:
        punishment_messages = "\n".join([f"@{username} has to add 2K steps today since they didn't complete their goals." for username in punished_users])
        db.reset_punishments(group_id)

    final_message = f"🌞 Good Morning!\n\nToday's Goals:\n{goal_messages}\n\n{punishment_messages}\n\n💪 {quote}"
    
    context.bot.send_message(chat_id=group_id, text=final_message, parse_mode=ParseMode.HTML)

def midnight_job(context):
    group_id = context.job.context

    # Process streaks, punishments, and resets
    db.process_midnight_tasks()

    # Prepare and send leaderboard
    leaderboard = db.get_leaderboard(group_id)
    leaderboard_message = "\n".join([f"@{username}: {streak} day streak" for username, streak in leaderboard])

    context.bot.send_message(chat_id=group_id, text=f"🌙 End of Day Leaderboard:\n\n{leaderboard_message}")


scheduler = BackgroundScheduler()

# Schedule morning reminders at 6 AM every day
scheduler.add_job(morning_reminder, 'cron', hour=6, minute=0, args=[updater.bot], kwargs={'context': TELEGRAM_GROUP_ID}, timezone=timezone('Asia/Kolkata'))

# Schedule midnight processing at 12 AM every day
scheduler.add_job(midnight_job, 'cron', hour=0, minute=0, args=[updater.bot], kwargs={'context': TELEGRAM_GROUP_ID}, timezone=timezone('Asia/Kolkata'))

scheduler.start()


if __name__ == '__main__':
    db.create_tables()  # Ensure tables are created on bot startup
    updater.start_polling()
    updater.idle()
