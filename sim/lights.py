"""Traffic light models."""
from __future__ import annotations

from dataclasses import dataclass, field

from sim.enums import Direction, LightPhase


@dataclass
class TrafficLight:
    direction: Direction
    phase: LightPhase = LightPhase.RED
    ticks_in_phase: int = 0

    def set_phase(self, new_phase: LightPhase) -> bool:
        """Return True if phase actually changed."""
        if self.phase != new_phase:
            self.phase = new_phase
            self.ticks_in_phase = 0
            return True
        return False

    def tick(self) -> None:
        self.ticks_in_phase += 1

    @property
    def is_green(self) -> bool:
        return self.phase == LightPhase.GREEN

    @property
    def is_red(self) -> bool:
        return self.phase == LightPhase.RED

    @property
    def is_amber_flash(self) -> bool:
        return self.phase == LightPhase.AMBER_FLASH


@dataclass
class PhaseConfig:
    """Defines one phase in a signal cycle."""

    name: str
    green_directions: list[Direction]
    duration_ticks: int = 60   # default 30 s at 2 ticks/s


@dataclass
class SignalPlan:
    """Ordered list of phases that constitute one cycle."""

    phases: list[PhaseConfig] = field(default_factory=list)
    yellow_ticks: int = 6      # 3 s clearance
    all_red_ticks: int = 4     # safe intergreen

    def __post_init__(self) -> None:
        if not self.phases:
            # Default 4-phase plan for a standard cross
            self.phases = [
                PhaseConfig("NS_GREEN", [Direction.NORTH, Direction.SOUTH], 60),
                PhaseConfig("EW_GREEN", [Direction.EAST, Direction.WEST], 60),
            ]
