# Test fixture that creates a temporary seeded SQLite database for each test,
# keeping tests isolated from the real parking database.
import pytest
from src import mcp_client
from data import seed
from src import db
from langgraph.checkpoint.memory import MemorySaver
from src import pipeline


@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    path = tmp_path / "parking.db"
    monkeypatch.setattr(seed, "DB_PATH", path)
    seed.seed()
    monkeypatch.setattr(db, "DB_PATH", path)
    return path

@pytest.fixture(autouse=True)
def no_real_mcp_calls(monkeypatch):
    async def fake_call(rid):
        return "skipped"
    monkeypatch.setattr(mcp_client, "_call", fake_call)

@pytest.fixture(autouse=True)
def memory_pipeline(monkeypatch):
    """Use an in-memory checkpointer in every test."""
    monkeypatch.setattr(pipeline, "_pipeline", pipeline.build_pipeline(MemorySaver()))