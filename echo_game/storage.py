"""SQLite progress/statistics storage, created automatically on first run."""
import sqlite3
from datetime import datetime
from .config import SAVE_DIR


def database_path():
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    return SAVE_DIR / 'echo_progress.db'


def initialize():
    with sqlite3.connect(database_path()) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            played_at TEXT NOT NULL,
            result TEXT NOT NULL,
            score INTEGER NOT NULL,
            time_seconds INTEGER NOT NULL,
            voice_commands INTEGER NOT NULL,
            errors INTEGER NOT NULL
        )''')
        db.commit()


def save_run(result: str, score: int, seconds: int, voice_count: int, errors: int):
    initialize()
    with sqlite3.connect(database_path()) as db:
        db.execute('INSERT INTO runs(played_at, result, score, time_seconds, voice_commands, errors) '
                   'VALUES (?, ?, ?, ?, ?, ?)',
                   (datetime.now().isoformat(timespec='seconds'), result, score,
                    seconds, voice_count, errors))
        db.commit()


def summary():
    initialize()
    with sqlite3.connect(database_path()) as db:
        total, best, wins = db.execute('SELECT COUNT(*), COALESCE(MAX(score),0), '
                                       "COALESCE(SUM(CASE WHEN result='won' THEN 1 ELSE 0 END),0) FROM runs").fetchone()
        recent = db.execute('SELECT result, score, time_seconds FROM runs '
                            'ORDER BY id DESC LIMIT 5').fetchall()
    return {'runs': total, 'best': best, 'wins': wins, 'recent': recent}
