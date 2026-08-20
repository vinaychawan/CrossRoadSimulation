"""
Fixed-cycle clock-driven controller.

Cycles through phases with dedicated turn arrows (left-hand drive):
  Phase 0: NS left arrows (protected left turn)
  Phase 1: NS green (straight + right)
  Phase 2: EW left arrows (protected left turn)
  Phase 3: EW green (straight + right)
  … repeat with yellow → all-red intergreen between major changes
"""
from __future__ import annotations

from algorithms import register
from sim.enums import Direction, LightPhase
from sim.intersection import Intersection

_NS = (Direction.NORTH, Direction.SOUTH)
_EW = (Direction.EAST, Direction.WEST)

# Phase definitions: (green_dirs, left_arrow_dirs, right_arrow_dirs)
_PHASES = [
    {"green": _NS, "left_arrow": _NS, "right_arrow": ()},   # NS left turn phase
    {"green": _NS, "left_arrow": (), "right_arrow": ()},     # NS through phase
    {"green": _EW, "left_arrow": _EW, "right_arrow": ()},   # EW left turn phase
    {"green": _EW, "left_arrow": (), "right_arrow": ()},     # EW through phase
]


@register
class FixedCycleController:
    name = "fixed_cycle"

    def __init__(
        self,
        green_ticks: int = 60,
        arrow_ticks: int = 20,
        yellow_ticks: int = 6,
        all_red_ticks: int = 4,
    ) -> None:
        self._green = green_ticks
        self._arrow = arrow_ticks
        self._yellow = yellow_ticks
        self._all_red = all_red_ticks
        self._phase_idx: int = 0
        self._elapsed: int = 0
        self._sub: str = "green"   # "green" | "yellow" | "all_red"

    def _phase_duration(self) -> int:
        if self._phase_idx % 2 == 0:
            return self._arrow
        return self._green

    def compute(
        self, tick: int, intersection: Intersection
    ) -> dict[Direction, LightPhase]:
        self._elapsed += 1
        commands: dict[Direction, LightPhase] = {}
        phase = _PHASES[self._phase_idx]

        if self._sub == "green":
            for d in phase["green"]:
                commands[d] = LightPhase.GREEN
            for d in Direction:
                if d not in phase["green"]:
                    commands[d] = LightPhase.RED

            # Set turn arrow lights
            for d in Direction:
                if d in phase.get("left_arrow", ()):
                    intersection.turn_lights[d]["left"].set_phase(LightPhase.LEFT_ARROW)
                else:
                    intersection.turn_lights[d]["left"].set_phase(LightPhase.RED)
                if d in phase.get("right_arrow", ()):
                    intersection.turn_lights[d]["right"].set_phase(LightPhase.RIGHT_ARROW)
                else:
                    intersection.turn_lights[d]["right"].set_phase(LightPhase.RED)

            if self._elapsed >= self._phase_duration():
                self._sub = "yellow"
                self._elapsed = 0

        elif self._sub == "yellow":
            for d in phase["green"]:
                commands[d] = LightPhase.YELLOW
            for d in Direction:
                if d not in phase["green"]:
                    commands[d] = LightPhase.RED
                intersection.turn_lights[d]["left"].set_phase(LightPhase.RED)
                intersection.turn_lights[d]["right"].set_phase(LightPhase.RED)

            if self._elapsed >= self._yellow:
                self._sub = "all_red"
                self._elapsed = 0

        else:  # all_red
            for d in Direction:
                commands[d] = LightPhase.RED
                intersection.turn_lights[d]["left"].set_phase(LightPhase.RED)
                intersection.turn_lights[d]["right"].set_phase(LightPhase.RED)
            if self._elapsed >= self._all_red:
                self._phase_idx = (self._phase_idx + 1) % len(_PHASES)
                self._sub = "green"
                self._elapsed = 0

        return commands
