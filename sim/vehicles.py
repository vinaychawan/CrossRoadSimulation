"""Vehicle domain models."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sim.enums import Direction, LanePosition, TurnIntention, VehicleState, VehicleType

# Physical constants per vehicle type
_VEHICLE_SPECS: dict[VehicleType, dict] = {
    VehicleType.CAR: {
        "length_m": 4.5,
        "max_speed_ms": 14.0,   # ~50 km/h within intersection zone
        "acceleration_ms2": 2.5,
        "deceleration_ms2": 4.0,
    },
    VehicleType.TRUCK: {
        "length_m": 12.0,
        "max_speed_ms": 10.0,
        "acceleration_ms2": 1.2,
        "deceleration_ms2": 2.5,
    },
}


@dataclass
class VehicleSpec:
    length_m: float
    max_speed_ms: float
    acceleration_ms2: float
    deceleration_ms2: float

    @classmethod
    def for_type(cls, vtype: VehicleType) -> VehicleSpec:
        return cls(**_VEHICLE_SPECS[vtype])


@dataclass
class Vehicle:
    """Represents a single vehicle moving through the intersection."""

    vehicle_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    vehicle_type: VehicleType = VehicleType.CAR
    direction: Direction = Direction.NORTH
    turn: TurnIntention = TurnIntention.STRAIGHT
    lane: LanePosition = LanePosition.MIDDLE
    state: VehicleState = VehicleState.QUEUED
    spawn_tick: int = 0
    green_tick: int | None = None   # tick when vehicle first saw green
    cross_tick: int | None = None   # tick when vehicle started crossing
    exit_tick: int | None = None
    queue_position: int = 0         # 0 = front of queue
    speed_ms: float = 0.0
    stops: int = 0                  # number of times stopped

    @property
    def spec(self) -> VehicleSpec:
        return VehicleSpec.for_type(self.vehicle_type)

    @property
    def wait_ticks(self) -> int:
        if self.green_tick is None:
            return 0
        return self.green_tick - self.spawn_tick

    @property
    def crossing_ticks(self) -> int:
        if self.cross_tick is None or self.exit_tick is None:
            return 0
        return self.exit_tick - self.cross_tick
