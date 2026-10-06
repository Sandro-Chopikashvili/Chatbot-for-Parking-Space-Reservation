from src import admin_agent as aa
from src import db, notifier


def test_parse_approve_and_reject():
    assert aa.parse_admin_reply("approve 5", llm_fallback=False) == ("approve", 5, "")
    assert aa.parse_admin_reply("Reject #7 lot is full", llm_fallback=False) == ("reject", 7, "lot is full")


def test_unparseable_reply_is_unknown():
    assert aa.parse_admin_reply("maybe later", llm_fallback=False)[0] == "unknown"


def test_apply_reply_updates_database(seeded_db):
    rid = db.create_reservation("A", "B", "AB-123-CD", "2030-01-01 10:00", "2030-01-01 12:00")
    assert aa.apply_admin_reply(f"reject {rid} full", llm_fallback=False) == f"Reservation #{rid} rejected."
    assert db.get_reservation(rid)["admin_comment"] == "full"
    assert "already rejected" in aa.apply_admin_reply(f"approve {rid}", llm_fallback=False)


def test_escalate_falls_back_to_template_when_agent_fails(seeded_db, tmp_path, monkeypatch):
    monkeypatch.setattr(notifier, "OUTBOX", tmp_path)
    monkeypatch.setattr(aa, "_get_agent", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    rid = db.create_reservation("A", "B", "AB-123-CD", "2030-01-01 10:00", "2030-01-01 12:00")
    assert aa.escalate(rid) is True
    assert "approve" in (tmp_path / f"request_{rid}.txt").read_text(encoding="utf-8")