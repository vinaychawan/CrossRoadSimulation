"""Stochastic vehicle traffic generator."""
from __future__ import annotations

import random
from dataclasses import dataclass

from sim.enums import Direction, VehicleType
from sim.vehicles import Vehicle


@dataclass
class ArrivalConfig:
    """Per-direction arrival configuration."""

    direction: Direction
    mean_interarrival_ticks: float = 20.0   # Poisson process mean gap
    car_fraction: float = 0.8               # rest are trucks


class TrafficGenerator:
    """Generates vehicle arrivals using a seeded RNG (Poisson inter-arrivals)."""

    def __init__(self, configs: list[ArrivalConfig], rng: random.Random) -> None:
        self._configs = {c.direction: c for c in configs}
        self._rng = rng
        # next_arrival_tick[dir] = tick when next vehicle should arrive
        self._next: dict[Direction, int] = {}
        self._init_next(tick=0)

    def _init_next(self, tick: int) -> None:
        for cfg in self._configs.values():
            self._next[cfg.direction] = tick + self._draw_gap(cfg)

    def _draw_gap(self, cfg: ArrivalConfig) -> int:
        return max(1, int(self._rng.expovariate(1.0 / cfg.mean_interarrival_ticks)))

    def tick(self, current_tick: int) -> list[Vehicle]:
        """Return list of vehicles that arrive this tick."""
        arrivals: list[Vehicle] = []
        for direction, cfg in self._configs.items():
            if current_tick >= self._next[direction]:
                vtype = (
                    VehicleType.CAR
                    if self._rng.random() < cfg.car_fraction
                    else VehicleType.TRUCK
                )
                arrivals.append(
                    Vehicle(
                        vehicle_id=format(self._rng.getrandbits(32), "08x"),
                        vehicle_type=vtype,
                        direction=direction,
                        spawn_tick=current_tick,
                    )
                )
                self._next[direction] = current_tick + self._draw_gap(cfg)
        return arrivals
