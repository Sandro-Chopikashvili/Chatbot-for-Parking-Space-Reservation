import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "parking.db"

SCHEMA = """
DROP TABLE IF EXISTS prices;
DROP TABLE IF EXISTS working_hours;
DROP TABLE IF EXISTS spaces;
DROP TABLE IF EXISTS reservations;

CREATE TABLE prices (zone TEXT PRIMARY KEY, hourly_rate REAL, daily_rate REAL);
CREATE TABLE working_hours (day TEXT PRIMARY KEY, open TEXT, close TEXT);
CREATE TABLE spaces (id INTEGER PRIMARY KEY, zone TEXT, status TEXT);
CREATE TABLE reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, surname TEXT, car_number TEXT,
    start_time TEXT, end_time TEXT,
    status TEXT DEFAULT 'pending',
    admin_comment TEXT,
    decided_at TEXT,
    recorded_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    conn.executemany("INSERT INTO prices VALUES (?,?,?)",
                     [("A", 4.0, 30.0), ("B", 3.0, 22.0), ("C", 3.5, 25.0)])

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    hours = [(d, "06:00", "23:00") for d in days[:5]] + \
            [("Saturday", "08:00", "23:00"), ("Sunday", "08:00", "20:00")]
    conn.executemany("INSERT INTO working_hours VALUES (?,?,?)", hours)

    random.seed(42)
    zones = ["A"] * 12 + ["B"] * 18 + ["C"] * 10
    conn.executemany("INSERT INTO spaces (zone, status) VALUES (?,?)",
                     [(z, random.choice(["free", "free", "occupied", "reserved"])) for z in zones])

    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH}")

if __name__ == "__main__":
    seed()

(Path(__file__).resolve().parent / "checkpoints.db").unlink(missing_ok=True)