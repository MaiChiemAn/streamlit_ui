import sqlite3
import time
from datetime import datetime

DB_FILE = "your_database.db"
INTERVAL_SECONDS = 3

SAMPLE_KEYWORDS = ["FOREST", "BEACH", "MOUNTAIN", "CITY", "DESERT"]
SAMPLE_TEAMS = ["teamA", "teamB", "teamC"]
SAMPLE_PLAYER = "tuan"

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS player_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_name TEXT NOT NULL,
    player_name TEXT NOT NULL,
    keyword TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(TABLE_SQL)
    conn.commit()


def insert_sample_row(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    team = SAMPLE_TEAMS[int(time.time()) % len(SAMPLE_TEAMS)]
    keyword = SAMPLE_KEYWORDS[int(time.time()) % len(SAMPLE_KEYWORDS)]
    cursor.execute(
        """
        INSERT INTO player_stats (team_name, player_name, keyword, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (team, SAMPLE_PLAYER, keyword, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    print(f"Inserted: team={team}, player={SAMPLE_PLAYER}, keyword={keyword}")


def main() -> None:
    print(
        f"Starting realtime inserter every {INTERVAL_SECONDS}s into player_stats. Press Ctrl+C to stop."
    )
    try:
        while True:
            with sqlite3.connect(DB_FILE) as conn:
                ensure_table(conn)
                insert_sample_row(conn)
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Updater stopped by user.")


if __name__ == "__main__":
    main()
