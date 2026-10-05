# Test fixture that creates a temporary seeded SQLite database for each test,
# keeping tests isolated from the real parking database.

import pytest

from data import seed
from src import db


@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    path = tmp_path / "parking.db"
    monkeypatch.setattr(seed, "DB_PATH", path)
    seed.seed()
    monkeypatch.setattr(db, "DB_PATH", path)
    return path