"""
Fixed-cycle clock-driven controller.

Cycles through phases without using traffic data:
  Phase 0: NS green  → yellow → all-red intergreen
  Phase 1: EW green  → yellow → all-red intergreen
  … repeat
"""
from __future__ import annotations

from dataclasses import dataclass, field

from algorithms import register, ControllerProtocol
from sim.enums import Direction, LightPhase
from sim.intersection import Intersection

_NS = (Direction.NORTH, Direction.SOUTH)
_EW = (Direction.EAST, Direction.WEST)
_PHASES = [_NS, _EW]


@register
class FixedCycleController:
    name = "fixed_cycle"

    def __init__(
        self,
        green_ticks: int = 60,
        yellow_ticks: int = 6,
        all_red_ticks: int = 4,
    ) -> None:
        self._green = green_ticks
        self._yellow = yellow_ticks
        self._all_red = all_red_ticks
        self._phase_idx: int = 0
        self._elapsed: int = 0
        self._sub: str = "green"   # "green" | "yellow" | "all_red"

    def compute(
        self, tick: int, intersection: Intersection
    ) -> dict[Direction, LightPhase]:
        self._elapsed += 1
        commands: dict[Direction, LightPhase] = {}

        if self._sub == "green":
            green_dirs = _PHASES[self._phase_idx]
            red_dirs = _PHASES[1 - self._phase_idx]
            for d in green_dirs:
                commands[d] = LightPhase.GREEN
            for d in red_dirs:
                commands[d] = LightPhase.RED
            if self._elapsed >= self._green:
                self._sub = "yellow"
                self._elapsed = 0

        elif self._sub == "yellow":
            green_dirs = _PHASES[self._phase_idx]
            red_dirs = _PHASES[1 - self._phase_idx]
            for d in green_dirs:
                commands[d] = LightPhase.YELLOW
            for d in red_dirs:
                commands[d] = LightPhase.RED
            if self._elapsed >= self._yellow:
                self._sub = "all_red"
                self._elapsed = 0

        else:  # all_red
            for d in Direction:
                commands[d] = LightPhase.RED
            if self._elapsed >= self._all_red:
                self._phase_idx = 1 - self._phase_idx
                self._sub = "green"
                self._elapsed = 0

        return commands
