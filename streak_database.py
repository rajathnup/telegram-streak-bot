import sqlite3

from datetime import datetime

conn = sqlite3.connect('streak_bot.db', check_same_thread=False)
cursor = conn.cursor()

def create_tables():
    cursor.execute(
        '''
        CREATE TABLE users (
        username TEXT NOT NULL,
        group_id INTEGER NOT NULL,
        monday_goal INTEGER NOT NULL,
        tuesday_goal INTEGER NOT NULL,
        wednesday_goal INTEGER NOT NULL,
        thursday_goal INTEGER NOT NULL,
        friday_goal INTEGER NOT NULL,
        saturday_goal INTEGER NOT NULL,
        sunday_goal INTEGER NOT NULL,
        current_streak INTEGER DEFAULT 0,
        today_tasks INTEGER DEFAULT 0,  -- Tracks today's task completions
        opt_out_days INTEGER DEFAULT 0, -- Days left to opt-out
        punishment INTEGER DEFAULT 0,   -- 1 = punishment required
        PRIMARY KEY (username, group_id)
);
        '''
    )
    conn.commit()

def register_user(username, group_id, goals):
    cursor.execute('''
        INSERT OR REPLACE INTO users (
            username, group_id, monday_goal, tuesday_goal, wednesday_goal,
            thursday_goal, friday_goal, saturday_goal, sunday_goal, current_streak, opt_out_days, punishment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
    ''', (username, group_id, *goals))
    conn.commit()

# -------------------- FETCH USER GOALS --------------------
def get_user_goals(username, group_id):
    cursor.execute('''
        SELECT monday_goal, tuesday_goal, wednesday_goal, thursday_goal, friday_goal, saturday_goal, sunday_goal
        FROM users
        WHERE username = ? AND group_id = ?
    ''', (username, group_id))
    return cursor.fetchone()

# -------------------- CHECK IF USER EXISTS --------------------
def user_exists(username, group_id):
    cursor.execute('''
        SELECT 1 FROM users WHERE username = ? AND group_id = ?
    ''', (username, group_id))
    return cursor.fetchone() is not None

def increment_today_tasks(username, group_id):
    cursor.execute('''
        UPDATE users
        SET today_tasks = today_tasks + 1
        WHERE username = ? AND group_id = ? AND opt_out_days = 0
    ''', (username, group_id))
    conn.commit()

def get_today_goal(username, group_id):
    day_of_week = datetime.now().strftime('%A').lower()  # e.g., 'monday'
    
    cursor.execute(f'''
        SELECT {day_of_week}_goal
        FROM users
        WHERE username = ? AND group_id = ?
    ''', (username, group_id))
    
    result = cursor.fetchone()
    return result[0] if result else None

def get_today_tasks(username, group_id):
    cursor.execute('''
        SELECT today_tasks FROM users
        WHERE username = ? AND group_id = ?
    ''', (username, group_id))
    
    result = cursor.fetchone()
    return result[0] if result else 0

def apply_opt_out(username, group_id, days):
    cursor.execute('''
        UPDATE users
        SET opt_out_days = ?
        WHERE username = ? AND group_id = ?
    ''', (days, username, group_id))
    conn.commit()

def apply_opt_in(username, group_id):
    cursor.execute('''
        UPDATE users
        SET opt_out_days = 0
        WHERE username = ? AND group_id = ?
    ''', (username, group_id))
    conn.commit()

def decrement_opt_out_days():
    cursor.execute('''
        UPDATE users
        SET opt_out_days = CASE
            WHEN opt_out_days > 0 THEN opt_out_days - 1
            ELSE 0
        END
    ''')
    conn.commit()

def process_midnight_tasks():
    day_of_week = datetime.now().strftime('%A').lower()  # Example: 'monday'

    # Fetch all users
    cursor.execute(f'''
        SELECT username, group_id, {day_of_week}_goal, today_tasks, opt_out_days
        FROM users
    ''')
    users = cursor.fetchall()

    # Process each user
    for user in users:
        username, group_id, today_goal, today_tasks, opt_out_days = user

        if opt_out_days == 0:  # Only process if not opted out
            if today_tasks >= today_goal:
                # User met goal, increment streak
                cursor.execute('''
                    UPDATE users
                    SET current_streak = current_streak + 1, punishment = 0
                    WHERE username = ? AND group_id = ?
                ''', (username, group_id))
            else:
                # User missed goal, reset streak, assign punishment
                cursor.execute('''
                    UPDATE users
                    SET current_streak = 0, punishment = 1
                    WHERE username = ? AND group_id = ?
                ''', (username, group_id))

    # Reset today_tasks for all users
    cursor.execute('''
        UPDATE users
        SET today_tasks = 0
    ''')

    # Decrement opt_out_days
    decrement_opt_out_days()

    conn.commit()

def get_users_with_punishment(group_id):
    cursor.execute('''
        SELECT username FROM users
        WHERE group_id = ? AND punishment = 1
    ''', (group_id,))
    return [row[0] for row in cursor.fetchall()]

def get_leaderboard(group_id):
    cursor.execute('''
        SELECT username, current_streak
        FROM users
        WHERE group_id = ?
        ORDER BY current_streak DESC
    ''', (group_id,))
    return cursor.fetchall()

def get_monthly_winner(group_id):
    cursor.execute('''
        SELECT username, current_streak
        FROM users
        WHERE group_id = ?
        ORDER BY current_streak DESC
        LIMIT 1
    ''', (group_id,))
    return cursor.fetchone()

def get_all_user_goals(group_id):
    day_of_week = datetime.now().strftime('%A').lower()

    cursor.execute(f'''
        SELECT username, {day_of_week}_goal
        FROM users
        WHERE group_id = ? AND opt_out_days = 0
    ''', (group_id,))

    return cursor.fetchall()

def reset_punishments(group_id):
    cursor.execute('''
        UPDATE users
        SET punishment = 0
        WHERE group_id = ?
    ''', (group_id,))
    conn.commit()
