from fastapi.testclient import TestClient

from src import db, mcp_server


def _approved(car="AB-123-CD"):
    rid = db.create_reservation("Ann", "Lee", car, "2030-01-01 10:00", "2030-01-01 12:00")
    db.decide_reservation(rid, "approved", "ok")
    return rid


def test_writes_line_in_required_format(seeded_db, tmp_path, monkeypatch):
    out = tmp_path / "approved.txt"
    monkeypatch.setattr(mcp_server, "OUTPUT_FILE", out)
    rid = _approved()
    assert mcp_server.write_approved(rid) == "recorded"
    parts = out.read_text(encoding="utf-8").strip().split(" | ")
    assert parts[:3] == ["Ann Lee", "AB-123-CD", "2030-01-01 10:00 to 2030-01-01 12:00"]
    assert len(parts) == 4 and parts[3]  # approval time present


def test_pending_unknown_and_duplicate_are_not_written(seeded_db, tmp_path, monkeypatch):
    out = tmp_path / "approved.txt"
    monkeypatch.setattr(mcp_server, "OUTPUT_FILE", out)
    pending = db.create_reservation("A", "B", "AB-123-CD", "2030-01-01 10:00", "2030-01-01 12:00")
    assert mcp_server.write_approved(pending) == "not_approved"
    assert mcp_server.write_approved(999) == "not_found"
    rid = _approved("ZZ-999-ZZ")
    assert mcp_server.write_approved(rid) == "recorded"
    assert mcp_server.write_approved(rid) == "already_recorded"
    assert len(out.read_text(encoding="utf-8").splitlines()) == 1


def test_fields_cannot_break_the_line_format(seeded_db, tmp_path, monkeypatch):
    out = tmp_path / "approved.txt"
    monkeypatch.setattr(mcp_server, "OUTPUT_FILE", out)
    rid = db.create_reservation("Evil | x", "Name\nINJECTED", "AB-123-CD",
                                "2030-01-01 10:00", "2030-01-01 12:00")
    db.decide_reservation(rid, "approved")
    mcp_server.write_approved(rid)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and len(lines[0].split(" | ")) == 4


def test_write_failure_releases_claim(seeded_db, tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server, "OUTPUT_FILE", tmp_path)  # a directory, so opening it fails
    rid = _approved()
    try:
        mcp_server.write_approved(rid)
    except Exception:
        pass
    assert db.claim_for_recording(rid) is True  # can be retried


def test_token_is_required(monkeypatch):
    monkeypatch.setenv("MCP_TOKEN", "secret")
    client = TestClient(mcp_server.app)
    assert client.post("/mcp").status_code == 401
    assert client.post("/mcp", headers={"Authorization": "Bearer wrong"}).status_code == 401