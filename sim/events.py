"""Append-only event log and KPI model."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from sim.enums import EventType


@dataclass
class SimEvent:
    tick: int
    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    run_id: str = ""

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "event_type": self.event_type.value,
            "payload": self.payload,
            "run_id": self.run_id,
        }


class EventLog:
    """Append-only in-memory event stream."""

    def __init__(self) -> None:
        self._events: list[SimEvent] = []

    def append(self, event: SimEvent) -> None:
        self._events.append(event)

    def all_events(self) -> list[SimEvent]:
        return list(self._events)

    def events_of_type(self, etype: EventType) -> list[SimEvent]:
        return [e for e in self._events if e.event_type == etype]

    def checksum(self) -> str:
        """SHA-256 of the canonical JSON representation for determinism testing.

        run_id is excluded because it is randomly generated per SimConfig
        instance and must not affect the determinism of simulation content.
        """
        raw = json.dumps(
            [
                {
                    "tick": e.tick,
                    "event_type": e.event_type.value,
                    "payload": e.payload,
                }
                for e in self._events
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(raw).hexdigest()

    def clear(self) -> None:
        self._events.clear()

    def __len__(self) -> int:
        return len(self._events)


@dataclass
class KPISnapshot:
    tick: int
    run_id: str
    avg_wait_ticks: float = 0.0
    max_wait_ticks: int = 0
    throughput_per_100_ticks: float = 0.0
    queue_lengths: dict[str, int] = field(default_factory=dict)
    total_stops: int = 0
    pct_null_control: float = 0.0
    vehicles_passed: int = 0
    vehicles_in_system: int = 0
