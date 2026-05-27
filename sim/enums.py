"""Domain enumerations and value types shared across sim/."""
from __future__ import annotations

from enum import Enum


class Direction(str, Enum):
    NORTH = "N"
    SOUTH = "S"
    EAST = "E"
    WEST = "W"


class LightPhase(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    AMBER_FLASH = "amber_flash"   # null-control fallback


class VehicleType(str, Enum):
    CAR = "car"
    TRUCK = "truck"


class VehicleState(str, Enum):
    QUEUED = "queued"
    MOVING = "moving"
    CROSSING = "crossing"
    EXITED = "exited"


class EventType(str, Enum):
    VEHICLE_SPAWN = "vehicle_spawn"
    VEHICLE_MOVE = "vehicle_move"
    VEHICLE_CROSS = "vehicle_cross"
    VEHICLE_EXIT = "vehicle_exit"
    LIGHT_CHANGE = "light_change"
    SAFETY_OVERRIDE = "safety_override"
    KPI_SAMPLE = "kpi_sample"
    PHASE_SWITCH = "phase_switch"
    ALGORITHM_SWITCH = "algorithm_switch"
    SIM_START = "sim_start"
    SIM_STOP = "sim_stop"
    SIM_RESET = "sim_reset"
