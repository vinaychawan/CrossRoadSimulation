"""SQLAlchemy 2.x ORM models.

Note: `from __future__ import annotations` is intentionally omitted here.
SQLAlchemy 2.x resolves `Mapped` annotations at class-creation time and
Python 3.14 changed `typing.Union.__getitem__` to a proper descriptor,
breaking SQLAlchemy's internal `Union.__getitem__(tuple)` call when
annotations are stored as strings.
Using concrete `Optional[...]` types (instead of `X | None` strings) and
avoiding the future import makes everything evaluate correctly.
"""
import datetime
import json
from typing import Any, List, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Layout(Base):
    """Intersection layout configuration."""

    __tablename__ = "layouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    scenarios: Mapped[List["Scenario"]] = relationship(back_populates="layout")

    @property
    def config(self) -> dict:
        return json.loads(self.config_json)


class Scenario(Base):
    """A named scenario referencing a layout + arrival configuration."""

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    layout_id: Mapped[int] = mapped_column(ForeignKey("layouts.id"))
    arrival_config_json: Mapped[str] = mapped_column(Text, default="{}")
    default_algorithm: Mapped[str] = mapped_column(String(64), default="fixed_cycle")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    layout: Mapped["Layout"] = relationship(back_populates="scenarios")
    runs: Mapped[List["Run"]] = relationship(back_populates="scenario")

    @property
    def arrival_config(self) -> dict:
        return json.loads(self.arrival_config_json)


class Run(Base):
    """One simulation run with its seed, config, and final KPI summary."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    scenario_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scenarios.id"), nullable=True)
    seed: Mapped[int] = mapped_column(Integer, default=42)
    algorithm: Mapped[str] = mapped_column(String(64))
    tick_step_ms: Mapped[int] = mapped_column(Integer, default=500)
    max_ticks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    event_log_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # KPI summary (final)
    avg_wait_ticks: Mapped[float] = mapped_column(Float, default=0.0)
    max_wait_ticks: Mapped[int] = mapped_column(Integer, default=0)
    throughput_per_100_ticks: Mapped[float] = mapped_column(Float, default=0.0)
    total_stops: Mapped[int] = mapped_column(Integer, default=0)
    pct_null_control: Mapped[float] = mapped_column(Float, default=0.0)
    vehicles_passed: Mapped[int] = mapped_column(Integer, default=0)

    scenario: Mapped[Optional["Scenario"]] = relationship(back_populates="runs")
    events: Mapped[List["EventRecord"]] = relationship(back_populates="run")
    recording: Mapped[Optional["Recording"]] = relationship(back_populates="run", uselist=False)


class EventRecord(Base):
    """Persisted event from the event log (event-sourcing)."""

    __tablename__ = "event_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id_fk: Mapped[str] = mapped_column(String(32), ForeignKey("runs.run_id"))
    tick: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    run: Mapped["Run"] = relationship(back_populates="events")


class Recording(Base):
    """Full recording of a run for playback."""

    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("runs.run_id"), unique=True)
    config_json: Mapped[str] = mapped_column(Text)
    snapshots_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    run: Mapped["Run"] = relationship(back_populates="recording")
