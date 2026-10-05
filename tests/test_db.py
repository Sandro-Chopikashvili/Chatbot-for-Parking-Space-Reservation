# Tests for the database layer:
# - Verify price and working-hours lookups.
# - Check handling of unknown parking zones.
# - Verify that new reservations are saved with a pending status.

from src import db


# Verify that zone lookup works regardless of letter case.
def test_price_lookup_is_case_insensitive(seeded_db):
    assert db.get_prices("c") == [
        {"zone": "C", "hourly_rate": 3.5, "daily_rate": 25.0}
    ]


# Verify that an unknown parking zone returns no results.
def test_unknown_zone_returns_empty(seeded_db):
    assert db.get_prices("Z") == []


# Verify that Sunday working hours are loaded correctly.
def test_sunday_hours(seeded_db):
    assert db.get_working_hours("sunday")[0]["close"] == "20:00"


# Verify that a newly created reservation is saved with "pending" status.
def test_reservation_is_saved_as_pending(seeded_db):
    rid = db.create_reservation(
        "A",
        "B",
        "AB-123-CD",
        "2030-01-01 10:00",
        "2030-01-01 12:00"
    )

    # Query the database using the generated reservation ID and check its status.
    assert db._query("SELECT status FROM reservations WHERE id = ?", (rid,))[0]["status"] == "pending"