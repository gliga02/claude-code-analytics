"""SQLAlchemy models for employees and telemetry events."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class Employee(Base):
    """Directory row from employees.csv, keyed by email."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    practice: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    level: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)

    events: Mapped[list["Event"]] = relationship(back_populates="employee")


class Event(Base):
    """Flattened telemetry event, linked to employees via user email."""

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_user_email_event_ts", "user_email", "event_ts"),
        Index("ix_events_practice_event_ts", "resource_practice", "event_ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_email: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    log_event_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    event_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    body: Mapped[str | None] = mapped_column(String(256), nullable=True)
    event_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_creation_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tool_decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_practice: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)

    employee: Mapped[Employee | None] = relationship(back_populates="events")
