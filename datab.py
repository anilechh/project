import sqlite3

conn = sqlite3.connect("reminders_aiogram.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    chat_id INTEGER NOT NULL,
    id INTEGER NOT NULL,
    text TEXT NOT NULL,
    remind_time DATETIME NOT NULL,
    creation_date DATE NOT NULL,
    is_daily BOOLEAN NOT NULL DEFAULT 0,
    week_day INTEGER,
    completed BOOLEAN NOT NULL DEFAULT 0,
    completion_date DATE,
    triggered BOOLEAN NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS statistics (
    chat_id INTEGER NOT NULL,
    date DATE NOT NULL,
    total INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, date)
)
""")
conn.commit()