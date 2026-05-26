"""
Null-control algorithm: all lights flash amber.

Also acts as the safe fallback when the safety checker intervenes.
"""
from __future__ import annotations

from algorithms import register, ControllerProtocol
from sim.enums import Direction, LightPhase
from sim.intersection import Intersection


@register
class NullController:
    name = "null_control"

    def compute(
        self, tick: int, intersection: Intersection
    ) -> dict[Direction, LightPhase]:
        return {d: LightPhase.AMBER_FLASH for d in Direction}
