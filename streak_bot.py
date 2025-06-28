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
from flask import Flask
from threading import Thread
import sqlite3

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)

load_dotenv()
TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_GROUP_ID = int(os.environ['TELEGRAM_GROUP_ID'])
ALLOWED_GROUP_ID = TELEGRAM_GROUP_ID

updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

app = Flask('')


@app.route('/')
def home():
    return "I'm alive!"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


@app.route('/db')
def view_db():
    import sqlite3
    conn = sqlite3.connect('streak_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    conn.close()

    response = "<h2>User Data:</h2><ul>"
    for row in rows:
        response += f"<li>{row}</li>"
    response += "</ul>"
    return response


def is_group_allowed(update):
    return update.effective_chat.id == ALLOWED_GROUP_ID


def restrict_group(func):

    def wrapper(update, context, *args, **kwargs):
        if not is_group_allowed(update):
            update.message.reply_text(
                "You are not authorized to use this bot here.")
            return
        return func(update, context, *args, **kwargs)

    return wrapper


def fetch_motivational_quote():
    # Fallback quotes in case API fails
    fallback_quotes = [
        "Success is not final, failure is not fatal: it is the courage to continue that counts. - Winston Churchill",
        "The only way to do great work is to love what you do. - Steve Jobs",
        "Don't watch the clock; do what it does. Keep going. - Sam Levenson",
        "The future depends on what you do today. - Mahatma Gandhi",
        "Push yourself, because no one else is going to do it for you.",
        "Great things never come from comfort zones.",
        "Dream it. Wish it. Do it.",
        "Success doesn't just find you. You have to go out and get it.",
        "Your limitation—it's only your imagination.",
        "Sometimes later becomes never. Do it now."
    ]

    try:
        print("Fetching motivational quote from ZenQuotes...")

        # ZenQuotes API endpoint for inspirational quotes
        response = requests.get('https://zenquotes.io/api/random', timeout=5)

        print(f"ZenQuotes API response status: {response.status_code}")

        if response.status_code == 200:
            quote_data = response.json()

            # ZenQuotes returns an array with one quote object
            if quote_data and len(quote_data) > 0:
                quote_text = quote_data[0]['q']  # 'q' is the quote text
                quote_author = quote_data[0]['a']  # 'a' is the author

                # Combine quote and author
                full_quote = f"{quote_text} - {quote_author}"

                print(f"Quote fetched successfully: {quote_text[:50]}...")
                return full_quote
            else:
                print("Empty response from ZenQuotes API")
        else:
            print(f"ZenQuotes API failed with status: {response.status_code}")

    except requests.exceptions.Timeout:
        print("ZenQuotes API timeout")
    except requests.exceptions.ConnectionError:
        print("ZenQuotes API connection error")
    except Exception as e:
        print(f"Error fetching quote from ZenQuotes: {e}")

    # Fallback to random local quote
    import random
    quote = random.choice(fallback_quotes)
    print(f"Using fallback quote: {quote[:50]}...")
    return quote


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
            update.message.reply_text(
                "Please provide 7 numbers for Monday to Sunday goals.")
            return
        db.register_user(username, group_id, goals)
        update.message.reply_text("Registered your goals successfully!")
    except:
        update.message.reply_text(
            "Please use the format: /register 1 2 3 4 5 6 7")


@restrict_group
def modify(update, context):
    username = update.effective_user.username
    group_id = update.effective_chat.id
    try:
        goals = list(map(int, context.args))
        if len(goals) != 7:
            update.message.reply_text(
                "Please provide 7 numbers for Monday to Sunday goals.")
            return
        db.modify_user_goals(username, group_id, goals)
        update.message.reply_text("Your goals have been updated successfully!")
    except:
        update.message.reply_text(
            "Please use the format: /modify 1 2 3 4 5 6 7")


@restrict_group
def checkin(update, context):
    username = update.effective_user.username
    group_id = update.effective_chat.id

    if db.user_exists(username, group_id):
        db.increment_today_tasks(username, group_id)
        update.message.reply_text(
            f"Check-in successful! Keep going, @{username}!")
    else:
        update.message.reply_text(
            "You need to register your goals first using /register.")


@restrict_group
def optout(update, context):
    username = update.effective_user.username
    group_id = update.effective_chat.id
    try:
        days = int(context.args[0])
        db.apply_opt_out(username, group_id, days)
        update.message.reply_text(
            f"Opted out for {days} day(s). We will miss you, get back soon!!")
    except:
        update.message.reply_text(
            "Please use the format: /optout <number_of_days>")


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
/checkin - Check-in one task completion.
/optout <days> - Opt-out for specified days.
/optin - Return to tracking.
/help - Show this help message.


"""
    update.message.reply_text(help_text)


dispatcher.add_handler(CommandHandler('register', register))
dispatcher.add_handler(CommandHandler('modify', modify))
dispatcher.add_handler(CommandHandler('optout', optout))
dispatcher.add_handler(CommandHandler('optin', optin))
dispatcher.add_handler(CommandHandler('help', help_command))
dispatcher.add_handler(CommandHandler('checkin', checkin))


def morning_reminder(context):
    group_id = context  # context IS the group_id
    print(f"Running morning reminder for group: {group_id}")

    try:
        # Fetch daily goals
        user_goals = db.get_all_user_goals(group_id)
        # Fetch punishments
        punished_users = db.get_users_with_punishment(group_id)
        # Fetch motivational quote
        quote = fetch_motivational_quote()

        # Build goals message
        goal_messages = "\n".join([
            f"@{username}: {goal} tasks today" for username, goal in user_goals
        ])

        # Build punishment message
        punishment_messages = ""
        if punished_users:
            punishment_messages = "\n".join([
                f"@{username} has to add 2K steps today since they didn't complete their goals."
                for username in punished_users
            ])
            db.reset_punishments(group_id)

        final_message = f"🌞 Good Morning!\n\nToday's Goals:\n{goal_messages}\n\n{punishment_messages}\n\n💪 {quote}"

        updater.bot.send_message(chat_id=group_id,
                                 text=final_message,
                                 parse_mode=ParseMode.HTML)

        print("Morning reminder sent successfully!")

    except Exception as e:
        print(f"Error sending morning reminder: {e}")


def midnight_job(context):
    group_id = context  # context IS the group_id
    print(f"Running midnight job for group: {group_id}")

    try:
        # Process streaks, punishments, and resets
        print("Processing midnight tasks...")
        db.process_midnight_tasks()
        print("Midnight tasks processed")

        # Prepare and send leaderboard
        print("Getting leaderboard...")
        leaderboard = db.get_leaderboard(group_id)
        print(f"Leaderboard data: {leaderboard}")

        if leaderboard:
            leaderboard_message = "\n".join([
                f"@{username}: {streak} day streak"
                for username, streak in leaderboard
            ])
        else:
            leaderboard_message = "No users registered yet."

        print(f"Sending leaderboard message: {leaderboard_message}")

        updater.bot.send_message(
            chat_id=group_id,
            text=f"🌙 End of Day Leaderboard:\n\n{leaderboard_message}")

        print("Midnight job completed successfully!")

    except Exception as e:
        print(f"Error in midnight job: {e}")
        import traceback
        traceback.print_exc()


def debug_database():
    try:
        with sqlite3.connect('streak_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            users = cursor.fetchall()
            print(f"Users in database: {users}")

            if users:
                for user in users:
                    print(f"User: {user}")
            else:
                print("No users found in database")
    except Exception as e:
        print(f"Database debug error: {e}")


scheduler = BackgroundScheduler()

# Morning reminder every minute
scheduler.add_job(morning_reminder,
                  'cron',
                  hour=6,
                  minute=0,
                  kwargs={'context': int(TELEGRAM_GROUP_ID)},
                  timezone=timezone('Asia/Kolkata'))

# Midnight job every minute
scheduler.add_job(midnight_job,
                  'cron',
                  hour=0,
                  minute=0,
                  kwargs={'context': int(TELEGRAM_GROUP_ID)},
                  timezone=timezone('Asia/Kolkata'))

scheduler.start()

if __name__ == '__main__':
    from streak_database import create_tables
    create_tables()
    debug_database()  # Add this line
    keep_alive()
    updater.start_polling()
    updater.idle()
