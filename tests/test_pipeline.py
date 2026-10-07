from fastapi.testclient import TestClient

from src import admin_agent as aa
from src import db, mcp_server, pipeline
from src.api import app

client = TestClient(app)
H = {"X-Admin-Token": "secret"}


def _make():
    return db.create_reservation("Ann", "Lee", "AB-123-CD", "2030-01-01 10:00", "2030-01-01 12:00")


def _next(rid):
    return pipeline.get_pipeline().get_state(pipeline._config(rid)).next


def test_pipeline_pauses_until_admin_decides(seeded_db, monkeypatch):
    monkeypatch.setattr(pipeline, "escalate", lambda rid: True)
    rid = _make()
    assert pipeline.start_pipeline(rid) is True
    assert _next(rid) == ("await_admin",)


def test_approval_resumes_pipeline_and_writes_file(seeded_db, tmp_path, monkeypatch):
    out = tmp_path / "approved.txt"
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setattr(mcp_server, "OUTPUT_FILE", out)
    monkeypatch.setattr(pipeline, "escalate", lambda rid: True)
    monkeypatch.setattr(aa.mcp_client, "record_approved", mcp_server.write_approved)
    rid = _make()
    pipeline.start_pipeline(rid)
    r = client.post(f"/admin/reservations/{rid}/decision",
                    json={"decision": "approved", "comment": "ok"}, headers=H)
    assert r.json()["file_status"] == "recorded"
    assert out.read_text(encoding="utf-8").startswith("Ann Lee | AB-123-CD")
    assert _next(rid) == ()


def test_rejection_ends_pipeline_without_file(seeded_db, tmp_path, monkeypatch):
    out = tmp_path / "approved.txt"
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setattr(mcp_server, "OUTPUT_FILE", out)
    monkeypatch.setattr(pipeline, "escalate", lambda rid: True)
    rid = _make()
    pipeline.start_pipeline(rid)
    r = client.post(f"/admin/reservations/{rid}/decision",
                    json={"decision": "rejected", "comment": "full"}, headers=H)
    assert r.json()["file_status"] == "not_needed"
    assert not out.exists() and _next(rid) == ()


def test_free_text_reply_resumes_pipeline(seeded_db, tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setattr(mcp_server, "OUTPUT_FILE", tmp_path / "approved.txt")
    monkeypatch.setattr(pipeline, "escalate", lambda rid: True)
    monkeypatch.setattr(aa.mcp_client, "record_approved", mcp_server.write_approved)
    rid = _make()
    pipeline.start_pipeline(rid)
    r = client.post("/admin/reply", json={"text": f"approve {rid}"}, headers=H)
    assert "approved" in r.json()["result"] and _next(rid) == ()


def test_decision_without_paused_run_uses_stage3_path(seeded_db, monkeypatch):
    monkeypatch.setattr(aa.mcp_client, "record_approved", lambda rid: "recorded")
    assert pipeline.resume_pipeline(_make(), "approved") == "recorded"


def test_start_pipeline_never_raises(seeded_db, monkeypatch):
    def boom(rid):
        raise RuntimeError("x")
    monkeypatch.setattr(pipeline, "escalate", boom)
    assert pipeline.start_pipeline(_make()) is False