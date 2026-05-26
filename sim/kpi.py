"""KPI calculator – computes metrics from event log + live state."""
from __future__ import annotations

from sim.enums import EventType, LightPhase
from sim.events import EventLog, KPISnapshot
from sim.intersection import Intersection
from sim.vehicles import Vehicle, VehicleState


class KPICalculator:
    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._passed_vehicles: list[Vehicle] = []
        self._null_control_ticks: int = 0
        self._total_ticks: int = 0

    def record_exit(self, vehicle: Vehicle) -> None:
        self._passed_vehicles.append(vehicle)

    def record_tick(self, intersection: Intersection) -> None:
        self._total_ticks += 1
        if all(
            light.is_amber_flash for light in intersection.lights.values()
        ):
            self._null_control_ticks += 1

    def snapshot(self, tick: int, intersection: Intersection, active_vehicles: list[Vehicle]) -> KPISnapshot:
        waits = [v.wait_ticks for v in self._passed_vehicles if v.wait_ticks > 0]
        stops = sum(v.stops for v in self._passed_vehicles + active_vehicles)
        return KPISnapshot(
            tick=tick,
            run_id=self._run_id,
            avg_wait_ticks=sum(waits) / len(waits) if waits else 0.0,
            max_wait_ticks=max(waits, default=0),
            throughput_per_100_ticks=(
                len(self._passed_vehicles) / self._total_ticks * 100
                if self._total_ticks
                else 0.0
            ),
            queue_lengths={
                d.value: ln.queue_length
                for d, ln in intersection.lanes.items()
            },
            total_stops=stops,
            pct_null_control=(
                self._null_control_ticks / self._total_ticks * 100
                if self._total_ticks
                else 0.0
            ),
            vehicles_passed=len(self._passed_vehicles),
            vehicles_in_system=len(active_vehicles),
        )
