"""Intersection layout and lane model."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from sim.enums import Direction, LanePosition, TurnIntention
from sim.lights import LightPhase, SignalPlan, TrafficLight
from sim.vehicles import Vehicle


@dataclass
class Lane:
    """A single approach lane on one arm of the intersection."""

    direction: Direction
    position: LanePosition = LanePosition.MIDDLE
    lane_id: str = ""
    capacity: int = 15
    _queue: deque[Vehicle] = field(default_factory=deque, repr=False)

    def __post_init__(self) -> None:
        if not self.lane_id:
            self.lane_id = f"{self.direction.value}_{self.position.value}"

    @property
    def allowed_turns(self) -> list[TurnIntention]:
        """Left-hand drive: left lane=left turn, middle=straight, right=right turn."""
        if self.position == LanePosition.LEFT:
            return [TurnIntention.LEFT]
        elif self.position == LanePosition.RIGHT:
            return [TurnIntention.RIGHT]
        return [TurnIntention.STRAIGHT]

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
    """Four-way intersection with 3 lanes per direction and traffic lights."""

    name: str = "default"
    lanes: dict[Direction, Lane] = field(default_factory=dict)
    multi_lanes: dict[Direction, dict[LanePosition, Lane]] = field(default_factory=dict)
    lights: dict[Direction, TrafficLight] = field(default_factory=dict)
    turn_lights: dict[Direction, dict[str, TrafficLight]] = field(default_factory=dict)
    signal_plan: SignalPlan = field(default_factory=SignalPlan)

    def __post_init__(self) -> None:
        for d in Direction:
            if d not in self.multi_lanes:
                self.multi_lanes[d] = {}
                for pos in LanePosition:
                    self.multi_lanes[d][pos] = Lane(direction=d, position=pos)
            # Keep backward-compat single lane reference (middle lane)
            if d not in self.lanes:
                self.lanes[d] = self.multi_lanes[d][LanePosition.MIDDLE]
            if d not in self.lights:
                self.lights[d] = TrafficLight(direction=d)
            if d not in self.turn_lights:
                self.turn_lights[d] = {
                    "left": TrafficLight(direction=d, phase=LightPhase.RED),
                    "right": TrafficLight(direction=d, phase=LightPhase.RED),
                }

    def get_lane_for_turn(self, direction: Direction, turn: TurnIntention) -> Lane:
        if turn == TurnIntention.LEFT:
            return self.multi_lanes[direction][LanePosition.LEFT]
        elif turn == TurnIntention.RIGHT:
            return self.multi_lanes[direction][LanePosition.RIGHT]
        return self.multi_lanes[direction][LanePosition.MIDDLE]

    def queue_length(self, direction: Direction) -> int:
        return sum(
            lane.queue_length for lane in self.multi_lanes[direction].values()
        )

    def total_queue(self) -> int:
        return sum(self.queue_length(d) for d in Direction)

    def phase_of(self, direction: Direction) -> LightPhase:
        return self.lights[direction].phase

    def set_all_amber_flash(self) -> None:
        for light in self.lights.values():
            light.set_phase(LightPhase.AMBER_FLASH)
        for d in Direction:
            for tl in self.turn_lights[d].values():
                tl.set_phase(LightPhase.AMBER_FLASH)

    def set_all_red(self) -> None:
        for light in self.lights.values():
            light.set_phase(LightPhase.RED)
        for d in Direction:
            for tl in self.turn_lights[d].values():
                tl.set_phase(LightPhase.RED)

    def tick_lights(self) -> None:
        for light in self.lights.values():
            light.tick()
        for d in Direction:
            for tl in self.turn_lights[d].values():
                tl.tick()
