"""Core simulation engine."""
from __future__ import annotations

import random
import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Protocol

from sim.enums import Direction, EventType, LanePosition, LightPhase, TurnIntention, VehicleState
from sim.events import EventLog, KPISnapshot, SimEvent
from sim.generator import ArrivalConfig, TrafficGenerator
from sim.intersection import Intersection
from sim.kpi import KPICalculator
from sim.lights import TrafficLight
from sim.vehicles import Vehicle

# Ticks a vehicle needs to cross the intersection box (type-dependent)
_CROSS_TICKS = {
    "car": 4,
    "bus": 6,
    "truck": 7,
}


class ControllerProtocol(Protocol):
    def compute(self, tick: int, intersection: Intersection) -> dict[Direction, LightPhase]:
        ...


class SafetyCheckerProtocol(Protocol):
    def check(
        self,
        commands: dict[Direction, LightPhase],
        intersection: Intersection,
    ) -> tuple[dict[Direction, LightPhase], list[dict]]:
        ...


@dataclass
class SimConfig:
    """All parameters needed to fully reproduce a simulation run."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    seed: int = 42
    tick_step_ms: int = 500          # wall-clock ms each tick represents
    max_ticks: int | None = None     # None = unlimited
    algorithm: str = "fixed_cycle"
    scenario_id: int | None = None
    arrival_configs: list[ArrivalConfig] = field(
        default_factory=lambda: [ArrivalConfig(d) for d in Direction]
    )
    kpi_sample_interval: int = 20    # emit KPI event every N ticks


class SimEngine:
    """
    Discrete-time simulation loop.

    The engine is algorithm-agnostic: it delegates phase decisions to a
    pluggable controller.  The safety checker sits between controller and lights.
    """

    def __init__(
        self,
        config: SimConfig,
        intersection: Intersection,
        controller: ControllerProtocol,
        safety_checker: SafetyCheckerProtocol,
    ) -> None:
        self.config = config
        self.intersection = intersection
        self.controller = controller
        self.safety_checker = safety_checker

        self._rng = random.Random(config.seed)
        self._generator = TrafficGenerator(config.arrival_configs, self._rng)
        self._event_log = EventLog()
        self._kpi = KPICalculator(config.run_id)

        self.tick: int = 0
        self.running: bool = False
        self._active_vehicles: list[Vehicle] = []
        self._crossing_vehicles: dict[str, int] = {}   # vid → ticks remaining

        # Listeners for real-time streaming
        self._listeners: list[Callable[[SimEvent], None]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_listener(self, cb: Callable[[SimEvent], None]) -> None:
        self._listeners.append(cb)

    def remove_listener(self, cb: Callable[[SimEvent], None]) -> None:
        with suppress(ValueError):
            self._listeners.remove(cb)

    def start(self) -> None:
        self.running = True
        self._emit(EventType.SIM_START, {})

    def stop(self) -> None:
        self.running = False
        self._emit(EventType.SIM_STOP, {"tick": self.tick})

    def reset(self) -> None:
        self.running = False
        self.tick = 0
        self._active_vehicles.clear()
        self._crossing_vehicles.clear()
        self._event_log.clear()
        self._kpi = KPICalculator(self.config.run_id)
        self._rng = random.Random(self.config.seed)
        self._generator = TrafficGenerator(self.config.arrival_configs, self._rng)
        for d in Direction:
            self.intersection.lanes[d]._queue.clear()
            for pos in LanePosition:
                self.intersection.multi_lanes[d][pos]._queue.clear()
        self.intersection.set_all_red()
        self._emit(EventType.SIM_RESET, {})

    def step(self) -> KPISnapshot | None:
        """Advance the simulation by exactly one tick. Returns KPI if sampled."""
        if not self.running:
            return None
        if self.config.max_ticks and self.tick >= self.config.max_ticks:
            self.stop()
            return None

        self.tick += 1

        # 1. Generate arrivals
        self._process_arrivals()

        # 2. Ask controller for desired light commands
        commands = self.controller.compute(self.tick, self.intersection)

        # 3. Pass through safety checker
        safe_commands, overrides = self.safety_checker.check(commands, self.intersection)

        # 4. Apply commands to lights
        self._apply_commands(safe_commands)

        # 5. Emit safety override events
        for override in overrides:
            self._emit(EventType.SAFETY_OVERRIDE, override)

        # 6. Tick lights
        self.intersection.tick_lights()

        # 7. Move vehicles
        self._move_vehicles()

        # 8. KPI tracking
        self._kpi.record_tick(self.intersection)

        # 9. Periodic KPI sample
        kpi: KPISnapshot | None = None
        if self.tick % self.config.kpi_sample_interval == 0:
            kpi = self._kpi.snapshot(self.tick, self.intersection, self._active_vehicles)
            self._emit(EventType.KPI_SAMPLE, _kpi_to_dict(kpi))

        return kpi

    def snapshot_state(self) -> dict:
        """Return a full state snapshot suitable for WebSocket broadcast."""
        return {
            "tick": self.tick,
            "run_id": self.config.run_id,
            "running": self.running,
            "algorithm": self.config.algorithm,
            "lights": {
                d.value: {
                    "phase": self.intersection.lights[d].phase.value,
                    "ticks_in_phase": self.intersection.lights[d].ticks_in_phase,
                    "left_arrow": self.intersection.turn_lights[d]["left"].phase.value,
                    "right_arrow": self.intersection.turn_lights[d]["right"].phase.value,
                }
                for d in Direction
            },
            "queues": {
                d.value: self.intersection.queue_length(d)
                for d in Direction
            },
            "lane_queues": {
                d.value: {
                    pos.value: self.intersection.multi_lanes[d][pos].queue_length
                    for pos in LanePosition
                }
                for d in Direction
            },
            "vehicles": [_vehicle_to_dict(v) for v in self._active_vehicles],
            "crossing": list(self._crossing_vehicles.keys()),
        }

    @property
    def event_log(self) -> EventLog:
        return self._event_log

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_arrivals(self) -> None:
        for vehicle in self._generator.tick(self.tick):
            lane = self.intersection.get_lane_for_turn(vehicle.direction, vehicle.turn)
            enqueued = lane.enqueue(vehicle)
            if enqueued:
                self._active_vehicles.append(vehicle)
                self._emit(
                    EventType.VEHICLE_SPAWN,
                    {
                        "vehicle_id": vehicle.vehicle_id,
                        "direction": vehicle.direction.value,
                        "type": vehicle.vehicle_type.value,
                        "turn": vehicle.turn.value,
                        "lane": vehicle.lane.value,
                    },
                )

    def _apply_commands(self, commands: dict[Direction, LightPhase]) -> None:
        for direction, phase in commands.items():
            changed = self.intersection.lights[direction].set_phase(phase)
            if changed:
                self._emit(
                    EventType.LIGHT_CHANGE,
                    {
                        "direction": direction.value,
                        "phase": phase.value,
                        "tick": self.tick,
                    },
                )

    def _move_vehicles(self) -> None:
        # Advance vehicles that are crossing
        finished_crossing: list[str] = []
        for vid, remaining in list(self._crossing_vehicles.items()):
            self._crossing_vehicles[vid] = remaining - 1
            if remaining - 1 <= 0:
                finished_crossing.append(vid)

        # Exit finished crossings
        for vid in finished_crossing:
            del self._crossing_vehicles[vid]
            vehicle = self._find_active(vid)
            if vehicle:
                vehicle.state = VehicleState.EXITED
                vehicle.exit_tick = self.tick
                self._active_vehicles.remove(vehicle)
                self._kpi.record_exit(vehicle)
                self._emit(
                    EventType.VEHICLE_EXIT,
                    {
                        "vehicle_id": vid,
                        "wait_ticks": vehicle.wait_ticks,
                        "stops": vehicle.stops,
                    },
                )

        # Release front-of-queue vehicles based on signal and turn
        for direction in Direction:
            light = self.intersection.lights[direction]
            turn_lights = self.intersection.turn_lights[direction]

            for lane_pos in LanePosition:
                lane = self.intersection.multi_lanes[direction][lane_pos]
                if lane.is_empty:
                    continue

                vehicle = lane.peek()
                if vehicle is None:
                    continue

                can_go = self._can_vehicle_proceed(vehicle, light, turn_lights)

                if can_go:
                    vehicle = lane.dequeue()
                    if vehicle:
                        vehicle.state = VehicleState.CROSSING
                        vehicle.cross_tick = self.tick
                        if vehicle.green_tick is None:
                            vehicle.green_tick = self.tick
                        cross_ticks = _CROSS_TICKS[vehicle.vehicle_type.value]
                        # Turning vehicles take slightly longer
                        if vehicle.turn != TurnIntention.STRAIGHT:
                            cross_ticks += 2
                        self._crossing_vehicles[vehicle.vehicle_id] = cross_ticks
                        self._emit(
                            EventType.VEHICLE_CROSS,
                            {
                                "vehicle_id": vehicle.vehicle_id,
                                "direction": direction.value,
                                "turn": vehicle.turn.value,
                            },
                        )
                else:
                    front = lane.peek()
                    if front and front.state == VehicleState.MOVING:
                        front.state = VehicleState.QUEUED
                        front.stops += 1

    def _can_vehicle_proceed(self, vehicle: Vehicle, main_light: TrafficLight, turn_lights: dict) -> bool:
        """Determine if a vehicle can proceed based on its turn and signal state."""
        # Left-hand drive: left turns get dedicated arrow phase
        if vehicle.turn == TurnIntention.LEFT:
            left_light = turn_lights["left"]
            return left_light.phase == LightPhase.LEFT_ARROW or main_light.is_green
        elif vehicle.turn == TurnIntention.RIGHT:
            right_light = turn_lights["right"]
            # Right turn on green allowed (no conflict in LHD), or dedicated arrow
            return right_light.phase == LightPhase.RIGHT_ARROW or main_light.is_green
        else:
            return main_light.is_green or main_light.is_amber_flash

    def _find_active(self, vid: str) -> Vehicle | None:
        return next((v for v in self._active_vehicles if v.vehicle_id == vid), None)

    def _emit(self, etype: EventType, payload: dict) -> None:
        event = SimEvent(tick=self.tick, event_type=etype, payload=payload, run_id=self.config.run_id)
        self._event_log.append(event)
        for cb in list(self._listeners):
            with suppress(Exception):  # noqa: BLE001
                cb(event)


def _vehicle_to_dict(v: Vehicle) -> dict:
    return {
        "vehicle_id": v.vehicle_id,
        "type": v.vehicle_type.value,
        "direction": v.direction.value,
        "turn": v.turn.value,
        "lane": v.lane.value,
        "state": v.state.value,
        "queue_position": v.queue_position,
        "wait_ticks": v.wait_ticks,
    }


def _kpi_to_dict(kpi: KPISnapshot) -> dict:
    return {
        "tick": kpi.tick,
        "avg_wait_ticks": kpi.avg_wait_ticks,
        "max_wait_ticks": kpi.max_wait_ticks,
        "throughput_per_100_ticks": kpi.throughput_per_100_ticks,
        "queue_lengths": kpi.queue_lengths,
        "total_stops": kpi.total_stops,
        "pct_null_control": kpi.pct_null_control,
        "vehicles_passed": kpi.vehicles_passed,
        "vehicles_in_system": kpi.vehicles_in_system,
    }
