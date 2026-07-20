"""Async persistence for the ledger.

Thin SQLAlchemy Core layer so the same code runs on SQLite (local, default) and
Postgres (deploy, via DATABASE_URL) with no query changes. Everything is scoped
by workspace_key. Timestamps are stored as ISO-8601 UTC strings for portability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (Column, DateTime, Integer, MetaData, String, Table, Text,
                        select)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from ledger.config import DATABASE_URL

_metadata = MetaData()

meetings = Table(
    "meetings", _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workspace_key", String(80), index=True, nullable=False),
    Column("title", Text, nullable=False),
    Column("record_md", Text, default=""),   # the generated record, for PDF export
    Column("created_at", DateTime(timezone=True), nullable=False),
)

decisions = Table(
    "decisions", _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workspace_key", String(80), index=True, nullable=False),
    Column("meeting_id", Integer, nullable=False),
    Column("what", Text, nullable=False),
    Column("why", Text, default=""),
    Column("owner", Text, default=""),
    Column("reversibility", String(20), default="unknown"),
    Column("status", String(20), default="active"),   # active | superseded
    Column("superseded_by", Integer, nullable=True),  # decisions.id that replaced it
    Column("created_at", DateTime(timezone=True), nullable=False),
)

commitments = Table(
    "commitments", _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workspace_key", String(80), index=True, nullable=False),
    Column("meeting_id", Integer, nullable=False),
    Column("who", Text, default=""),
    Column("what", Text, nullable=False),
    Column("due", Text, default=""),
    Column("status", String(20), default="open"),     # open | fulfilled
    Column("first_seen_at", DateTime(timezone=True), nullable=False),
    Column("fulfilled_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

risks = Table(
    "risks", _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workspace_key", String(80), index=True, nullable=False),
    Column("meeting_id", Integer, nullable=False),
    Column("what", Text, nullable=False),
    Column("owner", Text, default=""),
    Column("status", String(20), default="open"),     # open | resolved
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class OpenState:
    """The prior open items for a workspace, loaded before reconciliation."""
    decisions: list[dict[str, Any]] = field(default_factory=list)
    commitments: list[dict[str, Any]] = field(default_factory=list)
    risks: list[dict[str, Any]] = field(default_factory=list)


_engine: AsyncEngine | None = None
_initialized = False


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, future=True)
    return _engine


async def init_db() -> None:
    """Create tables if they don't exist. Cheap to call repeatedly (runs once)."""
    global _initialized
    if _initialized:
        return
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(_metadata.create_all)
    _initialized = True


async def create_meeting(workspace_key: str, title: str) -> int:
    engine = _get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            meetings.insert().values(
                workspace_key=workspace_key, title=title, created_at=_utcnow()
            )
        )
        return int(result.inserted_primary_key[0])


async def set_meeting_record(meeting_id: int, record_md: str) -> None:
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            meetings.update().where(meetings.c.id == meeting_id).values(record_md=record_md)
        )


async def get_meeting(meeting_id: int) -> dict[str, Any] | None:
    engine = _get_engine()
    async with engine.connect() as conn:
        row = await conn.execute(select(meetings).where(meetings.c.id == meeting_id))
        m = row.mappings().first()
        return dict(m) if m else None


async def load_open(workspace_key: str) -> OpenState:
    """Load the still-open decisions / commitments / risks for a workspace."""
    engine = _get_engine()
    async with engine.connect() as conn:
        d = await conn.execute(
            select(decisions).where(
                decisions.c.workspace_key == workspace_key,
                decisions.c.status == "active",
            )
        )
        c = await conn.execute(
            select(commitments).where(
                commitments.c.workspace_key == workspace_key,
                commitments.c.status == "open",
            )
        )
        r = await conn.execute(
            select(risks).where(
                risks.c.workspace_key == workspace_key,
                risks.c.status == "open",
            )
        )
        return OpenState(
            decisions=[dict(row) for row in d.mappings()],
            commitments=[dict(row) for row in c.mappings()],
            risks=[dict(row) for row in r.mappings()],
        )


async def load_all(workspace_key: str) -> dict[str, list[dict[str, Any]]]:
    """Load everything for a workspace (for the dashboard), newest first."""
    engine = _get_engine()
    async with engine.connect() as conn:
        out: dict[str, list[dict[str, Any]]] = {}
        for name, table in (("meetings", meetings), ("decisions", decisions),
                            ("commitments", commitments), ("risks", risks)):
            rows = await conn.execute(
                select(table)
                .where(table.c.workspace_key == workspace_key)
                .order_by(table.c.id.desc())
            )
            out[name] = [dict(row) for row in rows.mappings()]
        return out


async def insert_decision(workspace_key: str, meeting_id: int, item: dict[str, Any]) -> int:
    engine = _get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            decisions.insert().values(
                workspace_key=workspace_key,
                meeting_id=meeting_id,
                what=item.get("what", "").strip(),
                why=item.get("why", "").strip(),
                owner=item.get("owner", "").strip(),
                reversibility=(item.get("reversibility") or "unknown").strip().lower(),
                status="active",
                created_at=_utcnow(),
            )
        )
        return int(result.inserted_primary_key[0])


async def supersede_decision(prior_id: int, new_id: int) -> None:
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            decisions.update()
            .where(decisions.c.id == prior_id)
            .values(status="superseded", superseded_by=new_id)
        )


async def insert_commitment(workspace_key: str, meeting_id: int, item: dict[str, Any]) -> int:
    engine = _get_engine()
    async with engine.begin() as conn:
        now = _utcnow()
        result = await conn.execute(
            commitments.insert().values(
                workspace_key=workspace_key,
                meeting_id=meeting_id,
                who=item.get("who", "").strip(),
                what=item.get("what", "").strip(),
                due=item.get("due", "").strip(),
                status="open",
                first_seen_at=now,
                created_at=now,
            )
        )
        return int(result.inserted_primary_key[0])


async def fulfill_commitment(commitment_id: int) -> None:
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            commitments.update()
            .where(commitments.c.id == commitment_id)
            .values(status="fulfilled", fulfilled_at=_utcnow())
        )


async def insert_risk(workspace_key: str, meeting_id: int, item: dict[str, Any]) -> int:
    engine = _get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            risks.insert().values(
                workspace_key=workspace_key,
                meeting_id=meeting_id,
                what=item.get("what", "").strip(),
                owner=item.get("owner", "").strip(),
                status="open",
                created_at=_utcnow(),
            )
        )
        return int(result.inserted_primary_key[0])


async def resolve_risk(risk_id: int) -> None:
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            risks.update().where(risks.c.id == risk_id).values(status="resolved")
        )
