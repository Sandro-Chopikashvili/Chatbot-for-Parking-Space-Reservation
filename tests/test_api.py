from fastapi.testclient import TestClient

from src import db
from src.api import app

client = TestClient(app)
H = {"X-Admin-Token": "secret"}


def _make():
    return db.create_reservation("A", "B", "AB-123-CD", "2030-01-01 10:00", "2030-01-01 12:00")


def test_token_is_required(seeded_db, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    assert client.get("/admin/reservations").status_code == 401
    assert client.get("/admin/reservations", headers={"X-Admin-Token": "wrong"}).status_code == 401


def test_list_and_decide(seeded_db, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    rid = _make()
    assert len(client.get("/admin/reservations?status=pending", headers=H).json()) == 1
    ok = client.post(f"/admin/reservations/{rid}/decision",
                     json={"decision": "approved", "comment": "ok"}, headers=H)
    assert ok.status_code == 200 and ok.json()["status"] == "approved"


def test_double_decision_and_unknown_id(seeded_db, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    rid = _make()
    body = {"decision": "rejected", "comment": "no"}
    assert client.post(f"/admin/reservations/{rid}/decision", json=body, headers=H).status_code == 200
    assert client.post(f"/admin/reservations/{rid}/decision", json=body, headers=H).status_code == 409
    assert client.post("/admin/reservations/999/decision", json=body, headers=H).status_code == 404