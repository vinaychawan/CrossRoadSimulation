"""Unit tests for core simulation components."""
import pytest
from sim.vehicles import Vehicle, VehicleType
from sim.lights import TrafficLight, SignalPlan
from sim.enums import Direction, LightPhase, EventType
from sim.intersection import Intersection, Lane
from sim.events import EventLog, SimEvent
from sim.engine import SimConfig, SimEngine
from algorithms.switcher import AlgorithmSwitcher
from algorithms import discover
from safety.checker import SafetyChecker


discover()


# ── Vehicle ──────────────────────────────────────────────────────────────────

def test_vehicle_wait_ticks():
    v = Vehicle(spawn_tick=5, green_tick=15)
    assert v.wait_ticks == 10


def test_vehicle_spec_car():
    v = Vehicle(vehicle_type=VehicleType.CAR)
    assert v.spec.length_m == 4.5
    assert v.spec.acceleration_ms2 == 2.5


def test_vehicle_spec_truck():
    v = Vehicle(vehicle_type=VehicleType.TRUCK)
    assert v.spec.length_m == 12.0
    assert v.spec.acceleration_ms2 < 2.0


# ── Lane ─────────────────────────────────────────────────────────────────────

def test_lane_enqueue_dequeue():
    lane = Lane(Direction.NORTH, capacity=3)
    v1 = Vehicle()
    v2 = Vehicle()
    assert lane.enqueue(v1)
    assert lane.enqueue(v2)
    assert lane.queue_length == 2
    out = lane.dequeue()
    assert out is v1
    assert lane.queue_length == 1


def test_lane_capacity_enforced():
    lane = Lane(Direction.SOUTH, capacity=2)
    lane.enqueue(Vehicle())
    lane.enqueue(Vehicle())
    assert not lane.enqueue(Vehicle())  # over capacity


def test_lane_peek_does_not_remove():
    lane = Lane(Direction.EAST)
    v = Vehicle()
    lane.enqueue(v)
    assert lane.peek() is v
    assert lane.queue_length == 1


# ── TrafficLight ─────────────────────────────────────────────────────────────

def test_light_initial_red():
    light = TrafficLight(Direction.NORTH)
    assert light.is_red


def test_light_phase_change_resets_ticks():
    light = TrafficLight(Direction.NORTH)
    light.tick(); light.tick()
    changed = light.set_phase(LightPhase.GREEN)
    assert changed
    assert light.ticks_in_phase == 0
    assert light.is_green


def test_light_no_change_returns_false():
    light = TrafficLight(Direction.NORTH)
    assert not light.set_phase(LightPhase.RED)


# ── EventLog ─────────────────────────────────────────────────────────────────

def test_event_log_append_and_checksum():
    log = EventLog()
    e1 = SimEvent(tick=1, event_type=EventType.SIM_START, run_id="r1")
    e2 = SimEvent(tick=2, event_type=EventType.LIGHT_CHANGE, run_id="r1")
    log.append(e1); log.append(e2)
    cs1 = log.checksum()
    assert len(cs1) == 64
    # Checksum changes with new event
    log.append(SimEvent(tick=3, event_type=EventType.VEHICLE_SPAWN, run_id="r1"))
    assert log.checksum() != cs1


# ── SimEngine ────────────────────────────────────────────────────────────────

def test_engine_tick_increments(engine):
    engine.step()
    assert engine.tick == 1


def test_engine_stops_at_max_ticks():
    cfg = SimConfig(seed=1, max_ticks=10, algorithm="fixed_cycle")
    ix = Intersection()
    eng = SimEngine(cfg, ix, AlgorithmSwitcher("fixed_cycle"), SafetyChecker())
    eng.start()
    for _ in range(20):
        eng.step()
    assert not eng.running
    assert eng.tick <= 11


def test_engine_vehicles_pass_over_time():
    cfg = SimConfig(seed=7, max_ticks=200, algorithm="fixed_cycle")
    ix = Intersection()
    eng = SimEngine(cfg, ix, AlgorithmSwitcher("fixed_cycle"), SafetyChecker())
    eng.start()
    while eng.running:
        eng.step()
    kpi = eng._kpi.snapshot(eng.tick, ix, eng._active_vehicles)
    assert kpi.vehicles_passed > 0


def test_engine_snapshot_has_required_keys(engine):
    engine.step()
    snap = engine.snapshot_state()
    assert {"tick", "run_id", "running", "algorithm", "lights", "queues"}.issubset(snap.keys())


def test_engine_listener_called(engine):
    calls = []
    engine.add_listener(lambda e: calls.append(e))
    engine.step()
    assert len(calls) > 0


def test_algorithm_switch_inserts_all_red():
    """After requesting a switch, at least one tick must have all lights RED."""
    cfg = SimConfig(seed=2, algorithm="fixed_cycle")
    ix = Intersection()
    switcher = AlgorithmSwitcher("fixed_cycle")
    eng = SimEngine(cfg, ix, switcher, SafetyChecker())
    eng.start()
    # Run a few ticks to ensure we're not in startup all-red
    for _ in range(10):
        eng.step()
    switcher.request_switch("adaptive_cycle")
    all_red_seen = False
    for _ in range(8):
        eng.step()
        phases = [ix.lights[d].phase for d in Direction]
        if all(p == LightPhase.RED for p in phases):
            all_red_seen = True
    assert all_red_seen, "Expected all-red intergreen during algorithm switch"
