import sqlite3
from pathlib import Path

# Path to the SQLite database file.
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "parking.db"


# Execute a SQL query and return the results as a list of dictionaries.
def _query(sql: str, params: tuple = ()) -> list[dict]:
    # Open a connection to the SQLite database.
    conn = sqlite3.connect(DB_PATH)

    # Return rows as dictionary-like objects instead of tuples.
    conn.row_factory = sqlite3.Row

    try:
        # Execute the query with parameters and convert each row to a dictionary.
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        # Always close the database connection.
        conn.close()


# Get parking prices for a specific zone or for all zones.
def get_prices(zone: str | None = None) -> list[dict]:
    if zone:
        # Normalize the zone and filter the results by it.
        return _query("SELECT * FROM prices WHERE zone = ?", (zone.strip().upper(),))

    # Return prices for all zones when no zone is provided.
    return _query("SELECT * FROM prices")


# Get working hours for a specific day or for all days.
def get_working_hours(day: str | None = None) -> list[dict]:
    if day:
        # Normalize the day and filter the results by it.
        return _query(
            "SELECT * FROM working_hours WHERE day = ?",
            (day.strip().capitalize(),)
        )

    # Return working hours for all days when no day is provided.
    return _query("SELECT * FROM working_hours")


# Get the number of available parking spaces for each zone.
def get_availability(zone: str | None = None) -> list[dict]:
    # Start with a query that counts free spaces grouped by zone.
    sql = "SELECT zone, COUNT(*) AS free_spaces FROM spaces WHERE status = 'free'"
    params: tuple = ()

    if zone:
        # Filter the available spaces by the requested zone.
        sql += " AND zone = ?"
        params = (zone.strip().upper(),)

    # Execute the query and group the results by zone.
    return _query(sql + " GROUP BY zone", params)


# Create a new parking reservation and return its database ID.
def create_reservation(name, surname, car_number, start, end) -> int:
    # Open a connection to the SQLite database.
    conn = sqlite3.connect(DB_PATH)

    try:
        # Insert the booking information with a pending status.
        cur = conn.execute(
            "INSERT INTO reservations (name, surname, car_number, start_time, end_time, status) "
            "VALUES (?,?,?,?,?, 'pending')",
            (name, surname, car_number, start, end),
        )

        # Save the changes to the database.
        conn.commit()

        # Return the ID generated for the new reservation.
        return cur.lastrowid
    finally:
        # Always close the database connection.
        conn.close()