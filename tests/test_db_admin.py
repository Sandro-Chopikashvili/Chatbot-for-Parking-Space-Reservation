from src import db


def _make(car="AB-123-CD", start="2030-01-01 10:00", end="2030-01-01 12:00"):
    return db.create_reservation("A", "B", car, start, end)


def test_pending_can_be_decided_only_once(seeded_db):
    rid = _make()
    assert db.decide_reservation(rid, "approved", "ok") is True
    assert db.decide_reservation(rid, "rejected", "late") is False
    assert db.get_reservation(rid)["status"] == "approved"


def test_status_requires_matching_car_number(seeded_db):
    rid = _make()
    assert db.get_status(rid, "XX-000-XX") == {"found": False}
    assert db.get_status(rid, "ab-123-cd")["status"] == "pending"


def test_conflicts_only_count_approved(seeded_db):
    first = _make()
    second = _make(start="2030-01-01 11:00", end="2030-01-01 13:00")
    assert db.find_conflicts("2030-01-01 11:00", "2030-01-01 13:00", "ZZ-999-ZZ", second)["approved_overlapping"] == 0
    db.decide_reservation(first, "approved")
    assert db.find_conflicts("2030-01-01 11:00", "2030-01-01 13:00", "ZZ-999-ZZ", second)["approved_overlapping"] == 1