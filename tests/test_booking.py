# Tests for the booking validation logic:
# - Check valid and invalid car plate formats.
# - Check detection of missing booking fields.
# - Validate reservation start/end times and duration.
# - Verify that different datetime formats are normalized correctly.

from datetime import datetime

from src import booking as bk


# Fixed reference time used to test whether reservation times are in the past.
NOW = datetime(2026, 10, 5, 12, 0)


# Verify that a correctly formatted car plate is accepted.
def test_valid_plate_is_accepted():
    assert bk.valid_plate("ab-123-cd")


# Verify that an incorrectly formatted car plate is rejected.
def test_invalid_plate_rejected():
    assert not bk.valid_plate("12345")


# Verify that missing booking fields are correctly identified.
def test_missing_fields_detected():
    assert bk.missing({"name": "A"}) == ["surname", "car_number", "start", "end"]


# Verify that the reservation end time cannot be before the start time.
def test_end_before_start_rejected():
    b, errors = bk.validate(
        {"start": "2026-10-10 10:00", "end": "2026-10-10 08:00"},
        now=NOW
    )
    assert "end" not in b and errors


# Verify that a reservation cannot start in the past.
def test_past_start_rejected():
    b, errors = bk.validate(
        {"start": "2020-01-01 10:00"},
        now=NOW
    )
    assert "start" not in b and errors


# Verify that ISO datetime values are converted to the standard format.
def test_iso_datetime_is_normalized():
    b, errors = bk.validate(
        {"start": "2026-10-10T14:00:00"},
        now=NOW
    )
    assert b["start"] == "2026-10-10 14:00" and not errors


# Verify that reservations longer than 30 days are rejected.
def test_reservation_longer_than_30_days_rejected():
    b, errors = bk.validate(
        {"start": "2026-10-10 10:00", "end": "2026-12-10 10:00"},
        now=NOW
    )
    assert "end" not in b and errors