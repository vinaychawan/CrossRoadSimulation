"""
Safety checker layer.

Sits between the controller and the traffic lights.  Enforces hard safety
rules; if any rule is violated the output is overridden to null-control
(all amber-flash) and a human-readable explanation is logged.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sim.enums import Direction, LightPhase
from sim.intersection import Intersection

logger = logging.getLogger("safety")

# Conflicting direction pairs – these must never be simultaneously green
_CONFLICTING: list[tuple[Direction, Direction]] = [
    (Direction.NORTH, Direction.EAST),
    (Direction.NORTH, Direction.WEST),
    (Direction.SOUTH, Direction.EAST),
    (Direction.SOUTH, Direction.WEST),
    (Direction.EAST, Direction.NORTH),
    (Direction.WEST, Direction.NORTH),
]


@dataclass
class SafetyViolation:
    rule: str
    offending_command: str
    explanation: str
    override: str


class SafetyChecker:
    """
    Validates a set of proposed light commands before they are applied.

    Rules enforced:
    R1 – No conflicting greens: N↔E, N↔W, S↔E, S↔W cannot be green simultaneously.
    R2 – No direct RED→GREEN skip: a direction that has previously been GREEN must
         spend at least `all_red_intergreen_ticks` in RED before going GREEN again.
         (Does not apply on first startup since no traffic has cleared the box yet.)
    """

    def __init__(self, all_red_intergreen_ticks: int = 4) -> None:
        self._all_red_intergreen = all_red_intergreen_ticks
        self._interventions: int = 0
        # Track directions that have been GREEN at least once so R2 is only
        # enforced after the light has actually been active (not at startup).
        self._ever_been_green: set[Direction] = set()

    @property
    def total_interventions(self) -> int:
        return self._interventions

    def check(
        self,
        commands: dict[Direction, LightPhase],
        intersection: Intersection,
    ) -> tuple[dict[Direction, LightPhase], list[dict]]:
        """
        Returns (safe_commands, list_of_violation_dicts).

        If any violation is detected, safe_commands overrides to amber-flash
        for ALL directions.
        """
        violations: list[SafetyViolation] = []

        # R1 – Conflicting greens
        green_dirs = [d for d, p in commands.items() if p == LightPhase.GREEN]
        for a, b in _CONFLICTING:
            if a in green_dirs and b in green_dirs:
                violations.append(
                    SafetyViolation(
                        rule="R1_CONFLICTING_GREEN",
                        offending_command=f"GREEN({a.value}) and GREEN({b.value}) simultaneously",
                        explanation=(
                            f"Rule R1 violated: directions {a.value} and {b.value} "
                            f"are conflicting – granting both green would allow "
                            f"crossing paths to collide."
                        ),
                        override="null-control amber-flash on all directions",
                    )
                )

        # R2 – RED→GREEN skip (no yellow intergreen)
        # Only enforced for directions that have been GREEN before (skips startup).
        for direction, new_phase in commands.items():
            current = intersection.lights[direction].phase
            if (
                current == LightPhase.RED
                and new_phase == LightPhase.GREEN
                and direction in self._ever_been_green
            ):
                ticks_in_red = intersection.lights[direction].ticks_in_phase
                if ticks_in_red < self._all_red_intergreen:
                    violations.append(
                        SafetyViolation(
                            rule="R2_RED_TO_GREEN_SKIP",
                            offending_command=f"RED→GREEN on {direction.value} after {ticks_in_red} ticks",
                            explanation=(
                                f"Rule R2 violated: direction {direction.value} attempted "
                                f"to jump RED→GREEN after only {ticks_in_red} ticks in red "
                                f"(minimum intergreen = {self._all_red_intergreen} ticks). "
                                f"Conflicting vehicles may still be clearing the box."
                            ),
                            override="null-control amber-flash on all directions",
                        )
                    )

        if violations:
            self._interventions += 1
            for v in violations:
                logger.warning(
                    "SAFETY OVERRIDE | rule=%s | command=%s | explanation=%s | override=%s",
                    v.rule,
                    v.offending_command,
                    v.explanation,
                    v.override,
                )
            amber_commands = {d: LightPhase.AMBER_FLASH for d in Direction}
            violation_dicts = [
                {
                    "rule": v.rule,
                    "offending_command": v.offending_command,
                    "explanation": v.explanation,
                    "override": v.override,
                }
                for v in violations
            ]
            return amber_commands, violation_dicts

        # Track which directions have been GREEN (used for R2 on next call)
        for direction, phase in commands.items():
            if phase == LightPhase.GREEN:
                self._ever_been_green.add(direction)

        return commands, []

