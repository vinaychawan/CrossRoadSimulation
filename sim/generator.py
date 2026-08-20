"""Stochastic vehicle traffic generator."""
from __future__ import annotations

import random
from dataclasses import dataclass

from sim.enums import Direction, LanePosition, TurnIntention, VehicleType
from sim.vehicles import Vehicle


@dataclass
class ArrivalConfig:
    """Per-direction arrival configuration."""

    direction: Direction
    mean_interarrival_ticks: float = 20.0   # Poisson process mean gap
    car_fraction: float = 0.8               # rest are trucks
    left_turn_fraction: float = 0.2
    right_turn_fraction: float = 0.2
    # remaining fraction goes straight


_TURN_TO_LANE = {
    TurnIntention.LEFT: LanePosition.LEFT,
    TurnIntention.STRAIGHT: LanePosition.MIDDLE,
    TurnIntention.RIGHT: LanePosition.RIGHT,
}


class TrafficGenerator:
    """Generates vehicle arrivals using a seeded RNG (Poisson inter-arrivals)."""

    def __init__(self, configs: list[ArrivalConfig], rng: random.Random) -> None:
        self._configs = {c.direction: c for c in configs}
        self._rng = rng
        self._next: dict[Direction, int] = {}
        self._init_next(tick=0)

    def _init_next(self, tick: int) -> None:
        for cfg in self._configs.values():
            self._next[cfg.direction] = tick + self._draw_gap(cfg)

    def _draw_gap(self, cfg: ArrivalConfig) -> int:
        return max(1, int(self._rng.expovariate(1.0 / cfg.mean_interarrival_ticks)))

    def _pick_turn(self, cfg: ArrivalConfig) -> TurnIntention:
        r = self._rng.random()
        if r < cfg.left_turn_fraction:
            return TurnIntention.LEFT
        elif r < cfg.left_turn_fraction + cfg.right_turn_fraction:
            return TurnIntention.RIGHT
        return TurnIntention.STRAIGHT

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
                turn = self._pick_turn(cfg)
                lane = _TURN_TO_LANE[turn]
                arrivals.append(
                    Vehicle(
                        vehicle_id=format(self._rng.getrandbits(32), "08x"),
                        vehicle_type=vtype,
                        direction=direction,
                        turn=turn,
                        lane=lane,
                        spawn_tick=current_tick,
                    )
                )
                self._next[direction] = current_tick + self._draw_gap(cfg)
        return arrivals
