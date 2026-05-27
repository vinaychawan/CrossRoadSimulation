"""Intersection layout and lane model."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from sim.enums import Direction
from sim.lights import LightPhase, SignalPlan, TrafficLight
from sim.vehicles import Vehicle


@dataclass
class Lane:
    """A single approach lane on one arm of the intersection."""

    direction: Direction
    lane_id: str = ""
    capacity: int = 15
    _queue: deque[Vehicle] = field(default_factory=deque, repr=False)

    def __post_init__(self) -> None:
        if not self.lane_id:
            self.lane_id = f"{self.direction.value}_lane"

    def enqueue(self, vehicle: Vehicle) -> bool:
        if len(self._queue) >= self.capacity:
            return False
        vehicle.queue_position = len(self._queue)
        self._queue.append(vehicle)
        return True

    def dequeue(self) -> Vehicle | None:
        if not self._queue:
            return None
        v = self._queue.popleft()
        # Renumber remaining
        for i, qv in enumerate(self._queue):
            qv.queue_position = i
        return v

    @property
    def queue_length(self) -> int:
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def peek(self) -> Vehicle | None:
        return self._queue[0] if self._queue else None


@dataclass
class Intersection:
    """Four-way intersection composed of lanes and traffic lights."""

    name: str = "default"
    lanes: dict[Direction, Lane] = field(default_factory=dict)
    lights: dict[Direction, TrafficLight] = field(default_factory=dict)
    signal_plan: SignalPlan = field(default_factory=SignalPlan)

    def __post_init__(self) -> None:
        for d in Direction:
            if d not in self.lanes:
                self.lanes[d] = Lane(direction=d)
            if d not in self.lights:
                self.lights[d] = TrafficLight(direction=d)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def queue_length(self, direction: Direction) -> int:
        return self.lanes[direction].queue_length

    def total_queue(self) -> int:
        return sum(ln.queue_length for ln in self.lanes.values())

    def phase_of(self, direction: Direction) -> LightPhase:
        return self.lights[direction].phase

    def set_all_amber_flash(self) -> None:
        for light in self.lights.values():
            light.set_phase(LightPhase.AMBER_FLASH)

    def set_all_red(self) -> None:
        for light in self.lights.values():
            light.set_phase(LightPhase.RED)

    def tick_lights(self) -> None:
        for light in self.lights.values():
            light.tick()
