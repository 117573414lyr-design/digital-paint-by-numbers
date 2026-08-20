from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import sqlite3
import time
from typing import Any


@dataclass(slots=True)
class SampleRecord:
    id: int
    kind: str
    name: str
    source_path: str | None
    artifact_path: str | None
    score: float | None
    tags: list[str]
    metadata: dict[str, Any]
    created_at: float


class SampleStore:
    """SQLite store for approved, negative, and correction examples."""

    VALID_KINDS = {"reference", "negative", "correction", "profile"}

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                source_path TEXT,
                artifact_path TEXT,
                score REAL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_samples_kind ON samples(kind);
            CREATE INDEX IF NOT EXISTS idx_samples_created ON samples(created_at DESC);
            """
        )
        self.conn.commit()

    def add(
        self,
        *,
        kind: str,
        name: str,
        source_path: str | None = None,
        artifact_path: str | None = None,
        score: float | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        if kind not in self.VALID_KINDS:
            raise ValueError(f"invalid sample kind: {kind}")
        cursor = self.conn.execute(
            """INSERT INTO samples(kind,name,source_path,artifact_path,score,tags_json,metadata_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                kind,
                name,
                source_path,
                artifact_path,
                score,
                json.dumps(tags or [], ensure_ascii=False),
                json.dumps(metadata or {}, ensure_ascii=False),
                time.time(),
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def list(self, kind: str | None = None, limit: int = 100) -> list[SampleRecord]:
        if kind is None:
            rows = self.conn.execute("SELECT * FROM samples ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM samples WHERE kind=? ORDER BY created_at DESC LIMIT ?", (kind, limit)
            ).fetchall()
        return [self._to_record(row) for row in rows]

    def search(self, text: str, kind: str | None = None, limit: int = 50) -> list[SampleRecord]:
        pattern = f"%{text}%"
        if kind is None:
            rows = self.conn.execute(
                "SELECT * FROM samples WHERE name LIKE ? OR tags_json LIKE ? OR metadata_json LIKE ? ORDER BY created_at DESC LIMIT ?",
                (pattern, pattern, pattern, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM samples WHERE kind=? AND (name LIKE ? OR tags_json LIKE ? OR metadata_json LIKE ?) ORDER BY created_at DESC LIMIT ?",
                (kind, pattern, pattern, pattern, limit),
            ).fetchall()
        return [self._to_record(row) for row in rows]

    @staticmethod
    def _to_record(row: sqlite3.Row) -> SampleRecord:
        return SampleRecord(
            id=int(row["id"]),
            kind=str(row["kind"]),
            name=str(row["name"]),
            source_path=row["source_path"],
            artifact_path=row["artifact_path"],
            score=float(row["score"]) if row["score"] is not None else None,
            tags=json.loads(row["tags_json"]),
            metadata=json.loads(row["metadata_json"]),
            created_at=float(row["created_at"]),
        )

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "SampleStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
