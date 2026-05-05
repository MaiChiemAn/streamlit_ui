import sqlite3
from datetime import datetime

DB_FILE = "your_database.db"

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS player_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_name TEXT NOT NULL,
    player_name TEXT NOT NULL,
    keyword TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

SAMPLE_ROWS = [
    ("teamA", "tuan", "FOREST", "2026-05-04 23:02:22"),
    ("teamA", "tuan", "BEACH", "2026-05-04 23:02:38"),
    ("team_A", "tuan", "FOREST", "2026-05-05 09:23:03"),
]


def create_and_populate_db(db_path: str = DB_FILE) -> None:
    """Create the single-table schema `player_stats` and seed sample rows."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS player_stats")
    cursor.execute(TABLE_SQL)

    cursor.executemany(
        """
        INSERT INTO player_stats (team_name, player_name, keyword, created_at)
        VALUES (?, ?, ?, ?)
        """,
        SAMPLE_ROWS,
    )

    conn.commit()
    conn.close()

    print(f"Seeded {len(SAMPLE_ROWS)} rows into '{db_path}' at {datetime.now():%Y-%m-%d %H:%M:%S}")


if __name__ == "__main__":
    create_and_populate_db()
