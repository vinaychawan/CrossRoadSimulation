"""
Safe algorithm-switching controller.

Wraps an active controller and handles runtime algorithm changes by
inserting an all-red intergreen period before switching to the new
controller (satisfying the safety design requirement).
"""
from __future__ import annotations

import logging

from algorithms import ControllerProtocol, get
from sim.enums import Direction, LightPhase
from sim.intersection import Intersection

logger = logging.getLogger("algorithms.switcher")

_ALL_RED_INTERGREEN = 4  # ticks of all-red before new controller takes over


class AlgorithmSwitcher:
    """
    Wraps any controller and manages safe mid-run switching.

    Usage::

        switcher = AlgorithmSwitcher("fixed_cycle")
        switcher.request_switch("adaptive_cycle")   # safe switch queued
        commands = switcher.compute(tick, intersection)
    """

    def __init__(self, initial: str) -> None:
        self._active_name = initial
        self._active: ControllerProtocol = get(initial)()
        self._pending_name: str | None = None
        self._intergreen_remaining: int = 0

    @property
    def active_name(self) -> str:
        return self._active_name

    def request_switch(self, algorithm_name: str) -> None:
        if algorithm_name == self._active_name and self._pending_name is None:
            return
        get(algorithm_name)  # validate existence early
        self._pending_name = algorithm_name
        self._intergreen_remaining = _ALL_RED_INTERGREEN
        logger.info(
            "Algorithm switch requested: %s → %s, intergreen=%d ticks",
            self._active_name,
            algorithm_name,
            _ALL_RED_INTERGREEN,
        )

    def compute(
        self, tick: int, intersection: Intersection
    ) -> dict[Direction, LightPhase]:
        if self._intergreen_remaining > 0:
            self._intergreen_remaining -= 1
            if self._intergreen_remaining == 0 and self._pending_name:
                self._active_name = self._pending_name
                self._active = get(self._pending_name)()
                self._pending_name = None
                logger.info("Algorithm switched to: %s", self._active_name)
            return {d: LightPhase.RED for d in Direction}

        return self._active.compute(tick, intersection)
