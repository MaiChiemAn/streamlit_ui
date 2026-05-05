import sqlite3
import random
import time

DB_FILE = "your_database.db"
LOW_VALUE = 0
HIGH_VALUE = 30
INTERVAL_SECONDS = 3


def ensure_tables(conn: sqlite3.Connection) -> None:
    """Create Team_1..Team_10 tables with fixed id=1 row."""
    cursor = conn.cursor()
    for i in range(1, 11):
        table = f"Team_{i}"
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id INTEGER PRIMARY KEY,
                value INTEGER
            )
            """
        )
    conn.commit()


def upsert_random_values(conn: sqlite3.Connection) -> None:
    """Upsert a single row per team (overwrite existing, id fixed to 1)."""
    cursor = conn.cursor()
    for i in range(1, 11):
        table = f"Team_{i}"
        value = random.randint(LOW_VALUE, HIGH_VALUE)
        cursor.execute(f"INSERT OR REPLACE INTO {table} (id, value) VALUES (1, ?)", (value,))
        print(f"Set {table} (id=1) -> {value}")
    conn.commit()


def main() -> None:
    print(
        f"Starting updater: every {INTERVAL_SECONDS}s, values {LOW_VALUE}-{HIGH_VALUE} "
        "into Team_1..Team_10. Press Ctrl+C to stop."
    )
    try:
        while True:
            with sqlite3.connect(DB_FILE) as conn:
                ensure_tables(conn)
                upsert_random_values(conn)
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Updater stopped by user.")


if __name__ == "__main__":
    main()
