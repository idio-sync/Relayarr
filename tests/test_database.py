import asyncio
import tempfile
from pathlib import Path

import pytest

from bot.core.database import Database


@pytest.fixture
async def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    database = Database(db_path)
    await database.initialize()
    yield database
    await database.close()
    db_path.unlink(missing_ok=True)


class TestDatabase:
    async def test_initialize_creates_tables(self, db: Database):
        tables = await db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        table_names = {row["name"] for row in tables}
        assert "users" in table_names
        assert "request_log" in table_names

    async def test_add_and_get_user(self, db: Database):
        await db.execute(
            "INSERT INTO users (hostmask, role) VALUES (?, ?)",
            ("*!*@admin.host", "admin"),
        )
        rows = await db.fetch_all(
            "SELECT * FROM users WHERE hostmask = ?", ("*!*@admin.host",)
        )
        assert len(rows) == 1
        assert rows[0]["role"] == "admin"

    async def test_log_request(self, db: Database):
        await db.execute(
            "INSERT INTO request_log (nick, media_type, media_title, overseerr_id) "
            "VALUES (?, ?, ?, ?)",
            ("testuser", "movie", "Interstellar", 157336),
        )
        rows = await db.fetch_all(
            "SELECT * FROM request_log WHERE nick = ?", ("testuser",)
        )
        assert len(rows) == 1
        assert rows[0]["media_title"] == "Interstellar"
        assert rows[0]["overseerr_id"] == 157336

    async def test_fetch_one(self, db: Database):
        await db.execute(
            "INSERT INTO users (hostmask, role) VALUES (?, ?)",
            ("*!*@test.host", "user"),
        )
        row = await db.fetch_one(
            "SELECT * FROM users WHERE hostmask = ?", ("*!*@test.host",)
        )
        assert row is not None
        assert row["role"] == "user"

    async def test_fetch_one_returns_none(self, db: Database):
        row = await db.fetch_one(
            "SELECT * FROM users WHERE hostmask = ?", ("nonexistent",)
        )
        assert row is None
