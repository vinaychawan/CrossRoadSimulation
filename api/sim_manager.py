"""
Simulation manager: singleton that owns the running SimEngine.
WebSocket broadcasting is handled directly in main.py via threading.
"""
from __future__ import annotations

import logging
from typing import Any

from algorithms import discover
from algorithms.switcher import AlgorithmSwitcher
from safety.checker import SafetyChecker
from sim.engine import SimConfig, SimEngine
from sim.intersection import Intersection

logger = logging.getLogger("api.sim_manager")

discover()   # auto-load all algorithm plugins on startup


class SimManager:
    """Global simulation state holder."""

    def __init__(self) -> None:
        self._engine: SimEngine | None = None
        self._switcher: AlgorithmSwitcher | None = None
        self._config: SimConfig | None = None
        self._snapshots: list[dict] = []

    def create(self, config: SimConfig) -> str:
        intersection = Intersection()
        switcher = AlgorithmSwitcher(config.algorithm)
        checker = SafetyChecker()
        engine = SimEngine(
            config=config,
            intersection=intersection,
            controller=switcher,
            safety_checker=checker,
        )
        self._engine = engine
        self._switcher = switcher
        self._config = config
        self._snapshots = []
        return config.run_id

    def start(self) -> None:
        if self._engine:
            self._engine.start()

    def stop(self) -> None:
        if self._engine:
            self._engine.stop()

    def reset(self) -> None:
        if self._engine:
            self._engine.reset()
            self._snapshots = []

    def step(self) -> None:
        if self._engine and self._engine.running:
            self._engine.step()
            snap = self._engine.snapshot_state()
            self._snapshots.append(snap)

    def switch_algorithm(self, name: str) -> None:
        if self._switcher:
            self._switcher.request_switch(name)
            if self._config:
                self._config.algorithm = name

    @property
    def engine(self) -> SimEngine | None:
        return self._engine

    @property
    def config(self) -> SimConfig | None:
        return self._config

    @property
    def snapshots(self) -> list[dict]:
        return list(self._snapshots)


sim_manager = SimManager()
