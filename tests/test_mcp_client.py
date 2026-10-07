from src import mcp_client


def test_returns_server_status(monkeypatch):
    async def ok(rid):
        return "recorded"
    monkeypatch.setattr(mcp_client, "_call", ok)
    assert mcp_client.record_approved(1) == "recorded"


def test_retries_then_reports_unavailable(monkeypatch):
    calls = []

    async def boom(rid):
        calls.append(rid)
        raise ConnectionError("down")

    monkeypatch.setattr(mcp_client, "_call", boom)
    monkeypatch.setattr(mcp_client.time, "sleep", lambda s: None)
    assert mcp_client.record_approved(1, retries=3) == "unavailable"
    assert len(calls) == 3