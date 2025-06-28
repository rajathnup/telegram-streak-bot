import sqlite3
from datetime import datetime

DB_FILE = 'streak_bot.db'


def create_tables():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
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
                today_tasks INTEGER DEFAULT 0,
                opt_out_days INTEGER DEFAULT 0,
                punishment INTEGER DEFAULT 0,
                PRIMARY KEY (username, group_id)
            )
        ''')
        conn.commit()


def register_user(username, group_id, goals):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT OR REPLACE INTO users (
                username, group_id, monday_goal, tuesday_goal, wednesday_goal,
                thursday_goal, friday_goal, saturday_goal, sunday_goal, current_streak, opt_out_days, punishment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
        ''', (username, group_id, *goals))
        conn.commit()


def user_exists(username, group_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT 1 FROM users WHERE username = ? AND group_id = ?',
            (username, group_id))
        return cursor.fetchone() is not None


def increment_today_tasks(username, group_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE users
            SET today_tasks = today_tasks + 1
            WHERE username = ? AND group_id = ? AND opt_out_days = 0
        ''', (username, group_id))
        conn.commit()


def apply_opt_out(username, group_id, days):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE users
            SET opt_out_days = ?
            WHERE username = ? AND group_id = ?
        ''', (days, username, group_id))
        conn.commit()


def apply_opt_in(username, group_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE users
            SET opt_out_days = 0
            WHERE username = ? AND group_id = ?
        ''', (username, group_id))
        conn.commit()


def decrement_opt_out_days():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users
            SET opt_out_days = CASE
                WHEN opt_out_days > 0 THEN opt_out_days - 1
                ELSE 0
            END
        ''')
        conn.commit()


def process_midnight_tasks():
    day_of_week = datetime.now().strftime('%A').lower()

    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            with sqlite3.connect(DB_FILE, timeout=30.0) as conn:  # Add timeout
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT username, group_id, {day_of_week}_goal, today_tasks, opt_out_days
                    FROM users
                ''')
                users = cursor.fetchall()

                for user in users:
                    username, group_id, today_goal, today_tasks, opt_out_days = user

                    if opt_out_days == 0:
                        if today_tasks >= today_goal:
                            cursor.execute(
                                '''
                                UPDATE users
                                SET current_streak = current_streak + 1, punishment = 0
                                WHERE username = ? AND group_id = ?
                            ''', (username, group_id))
                        else:
                            cursor.execute(
                                '''
                                UPDATE users
                                SET current_streak = 0, punishment = 1
                                WHERE username = ? AND group_id = ?
                            ''', (username, group_id))

                cursor.execute('UPDATE users SET today_tasks = 0')

                # Update opt_out_days directly here instead of calling separate function
                cursor.execute('''
                    UPDATE users
                    SET opt_out_days = CASE
                        WHEN opt_out_days > 0 THEN opt_out_days - 1
                        ELSE 0
                    END
                ''')

                conn.commit()
                print("Midnight tasks processed successfully")
                break  # Success, exit retry loop

        except sqlite3.OperationalError as e:
            retry_count += 1
            print(f"Database lock error (attempt {retry_count}): {e}")
            if retry_count >= max_retries:
                raise
            import time
            time.sleep(1)  # Wait 1 second before retry


def get_users_with_punishment(group_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT username FROM users WHERE group_id = ? AND punishment = 1',
            (group_id, ))
        return [row[0] for row in cursor.fetchall()]


def get_leaderboard(group_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT username, current_streak FROM users WHERE group_id = ? ORDER BY current_streak DESC',
            (group_id, ))
        return cursor.fetchall()


def get_all_user_goals(group_id):
    day_of_week = datetime.now().strftime('%A').lower()
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f'SELECT username, {day_of_week}_goal FROM users WHERE group_id = ? AND opt_out_days = 0',
            (group_id, ))
        return cursor.fetchall()


def reset_punishments(group_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET punishment = 0 WHERE group_id = ?',
                       (group_id, ))
        conn.commit()


def modify_user_goals(username, group_id, goals):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE users
            SET monday_goal = ?, tuesday_goal = ?, wednesday_goal = ?, thursday_goal = ?,
                friday_goal = ?, saturday_goal = ?, sunday_goal = ?
            WHERE username = ? AND group_id = ?
        ''', (*goals, username, group_id))
        conn.commit()
