"""
Traffic-aware adaptive controller.

Extends green time for the active axis while its queue is long; yields
early when queues are short.  Includes dedicated left-turn arrow phases.
"""
from __future__ import annotations

from algorithms import register
from sim.enums import Direction, LightPhase
from sim.intersection import Intersection

_NS = (Direction.NORTH, Direction.SOUTH)
_EW = (Direction.EAST, Direction.WEST)
_PHASES = [_NS, _EW]


@register
class AdaptiveCycleController:
    name = "adaptive_cycle"

    def __init__(
        self,
        base_green: int = 40,
        min_green: int = 10,
        max_green: int = 120,
        arrow_ticks: int = 15,
        yellow_ticks: int = 6,
        all_red_ticks: int = 4,
        high_queue: int = 5,
        low_queue: int = 2,
        extension: int = 5,
        reduction: int = 5,
    ) -> None:
        self._base = base_green
        self._min = min_green
        self._max = max_green
        self._arrow = arrow_ticks
        self._yellow = yellow_ticks
        self._all_red = all_red_ticks
        self._high_q = high_queue
        self._low_q = low_queue
        self._ext = extension
        self._red = reduction

        self._phase_idx = 0
        self._elapsed = 0
        self._budget = base_green
        self._sub = "left_arrow"  # "left_arrow" | "green" | "yellow" | "all_red"

    def _axis_queue(self, intersection: Intersection, dirs: tuple) -> int:
        return sum(intersection.queue_length(d) for d in dirs)

    def compute(
        self, tick: int, intersection: Intersection
    ) -> dict[Direction, LightPhase]:
        self._elapsed += 1
        commands: dict[Direction, LightPhase] = {}
        active = _PHASES[self._phase_idx]
        inactive = _PHASES[1 - self._phase_idx]

        if self._sub == "left_arrow":
            # Protected left turn phase for the active axis
            for d in active:
                commands[d] = LightPhase.GREEN
                intersection.turn_lights[d]["left"].set_phase(LightPhase.LEFT_ARROW)
            for d in inactive:
                commands[d] = LightPhase.RED
                intersection.turn_lights[d]["left"].set_phase(LightPhase.RED)
            for d in Direction:
                intersection.turn_lights[d]["right"].set_phase(LightPhase.RED)

            if self._elapsed >= self._arrow:
                self._sub = "green"
                self._elapsed = 0

        elif self._sub == "green":
            # Adapt budget
            q = self._axis_queue(intersection, active)
            if q > self._high_q:
                self._budget = min(self._budget + self._ext, self._max)
            elif q < self._low_q:
                self._budget = max(self._budget - self._red, self._min)

            for d in active:
                commands[d] = LightPhase.GREEN
                intersection.turn_lights[d]["left"].set_phase(LightPhase.RED)
            for d in inactive:
                commands[d] = LightPhase.RED
                intersection.turn_lights[d]["left"].set_phase(LightPhase.RED)
            for d in Direction:
                intersection.turn_lights[d]["right"].set_phase(LightPhase.RED)

            if self._elapsed >= self._budget:
                self._sub = "yellow"
                self._elapsed = 0

        elif self._sub == "yellow":
            for d in active:
                commands[d] = LightPhase.YELLOW
            for d in inactive:
                commands[d] = LightPhase.RED
            for d in Direction:
                intersection.turn_lights[d]["left"].set_phase(LightPhase.RED)
                intersection.turn_lights[d]["right"].set_phase(LightPhase.RED)
            if self._elapsed >= self._yellow:
                self._sub = "all_red"
                self._elapsed = 0

        else:
            for d in Direction:
                commands[d] = LightPhase.RED
                intersection.turn_lights[d]["left"].set_phase(LightPhase.RED)
                intersection.turn_lights[d]["right"].set_phase(LightPhase.RED)
            if self._elapsed >= self._all_red:
                self._phase_idx = 1 - self._phase_idx
                self._budget = self._base
                self._sub = "left_arrow"
                self._elapsed = 0

        return commands
