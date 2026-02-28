from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    hostmask TEXT PRIMARY KEY,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS request_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nick TEXT NOT NULL,
    media_type TEXT NOT NULL,
    media_title TEXT NOT NULL,
    overseerr_id INTEGER,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: Path):
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def execute(self, sql: str, params: tuple = ()) -> None:
        await self._conn.execute(sql, params)
        await self._conn.commit()

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
