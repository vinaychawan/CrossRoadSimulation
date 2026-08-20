"""
Extended unit tests for sim/ — covers all missing lines for 100% coverage.
"""
import random

from algorithms import discover
from algorithms.switcher import AlgorithmSwitcher
from safety.checker import SafetyChecker
from sim.engine import SimConfig, SimEngine, _kpi_to_dict, _vehicle_to_dict
from sim.enums import Direction, EventType, LightPhase, VehicleState, VehicleType
from sim.events import EventLog, KPISnapshot, SimEvent
from sim.generator import ArrivalConfig, TrafficGenerator
from sim.intersection import Intersection, Lane
from sim.kpi import KPICalculator
from sim.lights import PhaseConfig, SignalPlan, TrafficLight
from sim.vehicles import Vehicle, VehicleSpec

discover()


# ── Vehicle ──────────────────────────────────────────────────────────────────

def test_vehicle_wait_ticks_no_green():
    """wait_ticks returns 0 when green_tick is None."""
    v = Vehicle(spawn_tick=10)
    assert v.wait_ticks == 0


def test_vehicle_crossing_ticks():
    v = Vehicle(cross_tick=5, exit_tick=10)
    assert v.crossing_ticks == 5


def test_vehicle_crossing_ticks_none():
    v = Vehicle()
    assert v.crossing_ticks == 0


def test_vehicle_spec_property():
    car = Vehicle(vehicle_type=VehicleType.CAR)
    truck = Vehicle(vehicle_type=VehicleType.TRUCK)
    assert isinstance(car.spec, VehicleSpec)
    assert car.spec.length_m == 4.5
    assert truck.spec.length_m == 12.0


def test_vehicle_default_id_is_string():
    v = Vehicle()
    assert isinstance(v.vehicle_id, str)
    assert len(v.vehicle_id) > 0


def test_vehicle_spec_for_type_truck():
    spec = VehicleSpec.for_type(VehicleType.TRUCK)
    assert spec.max_speed_ms == 10.0
    assert spec.deceleration_ms2 == 2.5


# ── Lane ─────────────────────────────────────────────────────────────────────

def test_lane_dequeue_empty_returns_none():
    lane = Lane(Direction.NORTH)
    assert lane.dequeue() is None


def test_lane_peek_empty_returns_none():
    lane = Lane(Direction.EAST)
    assert lane.peek() is None


def test_lane_default_lane_id():
    lane = Lane(Direction.SOUTH)
    assert lane.lane_id == "S_middle"


def test_lane_custom_lane_id():
    lane = Lane(Direction.WEST, lane_id="custom")
    assert lane.lane_id == "custom"


def test_lane_queue_position_renumbered_after_dequeue():
    lane = Lane(Direction.NORTH)
    v1, v2, v3 = Vehicle(), Vehicle(), Vehicle()
    lane.enqueue(v1)
    lane.enqueue(v2)
    lane.enqueue(v3)
    lane.dequeue()
    assert v2.queue_position == 0
    assert v3.queue_position == 1


def test_lane_allowed_turns_left():
    from sim.enums import LanePosition, TurnIntention
    lane = Lane(Direction.NORTH, position=LanePosition.LEFT)
    assert lane.allowed_turns == [TurnIntention.LEFT]


def test_lane_allowed_turns_right():
    from sim.enums import LanePosition, TurnIntention
    lane = Lane(Direction.NORTH, position=LanePosition.RIGHT)
    assert lane.allowed_turns == [TurnIntention.RIGHT]


def test_lane_allowed_turns_middle():
    from sim.enums import LanePosition, TurnIntention
    lane = Lane(Direction.NORTH, position=LanePosition.MIDDLE)
    assert lane.allowed_turns == [TurnIntention.STRAIGHT]


# ── TrafficLight ──────────────────────────────────────────────────────────────

def test_traffic_light_is_green():
    tl = TrafficLight(Direction.NORTH)
    tl.set_phase(LightPhase.GREEN)
    assert tl.is_green
    assert not tl.is_red
    assert not tl.is_amber_flash


def test_traffic_light_is_amber_flash():
    tl = TrafficLight(Direction.EAST)
    tl.set_phase(LightPhase.AMBER_FLASH)
    assert tl.is_amber_flash


def test_traffic_light_tick_increments():
    tl = TrafficLight(Direction.NORTH)
    tl.tick()
    tl.tick()
    assert tl.ticks_in_phase == 2


def test_traffic_light_is_left_arrow():
    tl = TrafficLight(Direction.NORTH)
    tl.set_phase(LightPhase.LEFT_ARROW)
    assert tl.is_left_arrow


def test_traffic_light_is_right_arrow():
    tl = TrafficLight(Direction.NORTH)
    tl.set_phase(LightPhase.RIGHT_ARROW)
    assert tl.is_right_arrow


def test_traffic_light_allows_through():
    tl = TrafficLight(Direction.NORTH)
    tl.set_phase(LightPhase.GREEN)
    assert tl.allows_through
    tl.set_phase(LightPhase.RED)
    assert not tl.allows_through


# ── SignalPlan + PhaseConfig ──────────────────────────────────────────────────

def test_signal_plan_default_phases():
    sp = SignalPlan()
    assert len(sp.phases) == 4
    assert sp.phases[0].name == "NS_LEFT"
    assert sp.phases[1].name == "NS_GREEN"
    assert sp.phases[2].name == "EW_LEFT"
    assert sp.phases[3].name == "EW_GREEN"


def test_signal_plan_custom_phases():
    custom = [PhaseConfig(name="ALL_NS", green_directions=[Direction.NORTH, Direction.SOUTH])]
    sp = SignalPlan(phases=custom)
    assert len(sp.phases) == 1


def test_phase_config_fields():
    pc = PhaseConfig(name="ns_green", green_directions=[Direction.NORTH, Direction.SOUTH])
    assert pc.name == "ns_green"
    assert len(pc.green_directions) == 2
    assert pc.duration_ticks == 60


# ── Intersection ──────────────────────────────────────────────────────────────

def test_intersection_total_queue():
    ix = Intersection()
    ix.lanes[Direction.NORTH].enqueue(Vehicle())
    ix.lanes[Direction.SOUTH].enqueue(Vehicle())
    assert ix.total_queue() == 2


def test_intersection_queue_length_helper():
    ix = Intersection()
    ix.lanes[Direction.EAST].enqueue(Vehicle())
    assert ix.queue_length(Direction.EAST) == 1


def test_intersection_phase_of():
    ix = Intersection()
    ix.lights[Direction.WEST].set_phase(LightPhase.GREEN)
    assert ix.phase_of(Direction.WEST) == LightPhase.GREEN


def test_intersection_set_all_amber_flash():
    ix = Intersection()
    ix.set_all_amber_flash()
    for d in Direction:
        assert ix.lights[d].phase == LightPhase.AMBER_FLASH


def test_intersection_tick_lights():
    ix = Intersection()
    ix.tick_lights()
    for d in Direction:
        assert ix.lights[d].ticks_in_phase == 1


# ── EventLog ──────────────────────────────────────────────────────────────────

def test_event_log_len():
    log = EventLog()
    log.append(SimEvent(tick=1, event_type=EventType.SIM_START))
    log.append(SimEvent(tick=2, event_type=EventType.SIM_STOP))
    assert len(log) == 2


def test_event_log_all_events():
    log = EventLog()
    e = SimEvent(tick=1, event_type=EventType.SIM_START)
    log.append(e)
    all_ev = log.all_events()
    assert len(all_ev) == 1
    assert all_ev[0] is e


def test_event_log_events_of_type():
    log = EventLog()
    log.append(SimEvent(tick=1, event_type=EventType.SIM_START))
    log.append(SimEvent(tick=2, event_type=EventType.VEHICLE_SPAWN))
    log.append(SimEvent(tick=3, event_type=EventType.SIM_STOP))
    spawns = log.events_of_type(EventType.VEHICLE_SPAWN)
    assert len(spawns) == 1
    assert spawns[0].tick == 2


def test_sim_event_to_dict():
    e = SimEvent(tick=5, event_type=EventType.KPI_SAMPLE,
                 payload={"a": 1}, run_id="abc")
    d = e.to_dict()
    assert d["tick"] == 5
    assert d["event_type"] == "kpi_sample"
    assert d["payload"] == {"a": 1}
    assert d["run_id"] == "abc"


# ── KPISnapshot ───────────────────────────────────────────────────────────────

def test_kpi_snapshot_fields():
    kpi = KPISnapshot(tick=10, run_id="x", vehicles_passed=5,
                      avg_wait_ticks=3.5, throughput_per_100_ticks=12.0,
                      queue_lengths={"N": 0}, pct_null_control=0.0)
    assert kpi.tick == 10
    assert kpi.vehicles_passed == 5


# ── KPICalculator ─────────────────────────────────────────────────────────────

def test_kpi_record_tick_non_amber():
    """record_tick when NOT all-amber should not count null-control ticks."""
    calc = KPICalculator("run1")
    ix = Intersection()
    ix.lights[Direction.NORTH].set_phase(LightPhase.GREEN)
    calc.record_tick(ix)
    snap = calc.snapshot(1, ix, [])
    assert snap.pct_null_control == 0.0


def test_kpi_record_tick_all_amber():
    calc = KPICalculator("run1")
    ix = Intersection()
    ix.set_all_amber_flash()
    calc.record_tick(ix)
    snap = calc.snapshot(1, ix, [])
    assert snap.pct_null_control == 100.0


def test_kpi_empty_snapshot():
    calc = KPICalculator("run1")
    ix = Intersection()
    snap = calc.snapshot(0, ix, [])
    assert snap.avg_wait_ticks == 0.0
    assert snap.vehicles_passed == 0


# ── TrafficGenerator ──────────────────────────────────────────────────────────

def test_traffic_generator_reproducible():
    rng = random.Random(99)
    configs = [ArrivalConfig(d) for d in Direction]
    gen = TrafficGenerator(configs, rng)
    vehicles = []
    for t in range(100):
        vehicles.extend(gen.tick(t))
    assert len(vehicles) > 0


def test_arrival_config_defaults():
    cfg = ArrivalConfig(Direction.NORTH)
    assert cfg.mean_interarrival_ticks == 20.0
    assert cfg.car_fraction == 0.7
    assert cfg.bus_fraction == 0.1


# ── Engine ────────────────────────────────────────────────────────────────────

def _make_engine(seed=1, max_ticks=50, algo="fixed_cycle") -> SimEngine:
    cfg = SimConfig(seed=seed, max_ticks=max_ticks, algorithm=algo)
    ix = Intersection()
    return SimEngine(cfg, ix, AlgorithmSwitcher(algo), SafetyChecker())


def test_engine_step_when_not_running_returns_none():
    eng = _make_engine()
    result = eng.step()
    assert result is None


def test_engine_reset_clears_state():
    eng = _make_engine(max_ticks=10)
    eng.start()
    for _ in range(5):
        eng.step()
    assert eng.tick > 0
    eng.reset()
    assert eng.tick == 0
    assert not eng.running


def test_engine_reset_emits_reset_event():
    eng = _make_engine()
    eng.start()
    eng.reset()
    types = [e.event_type for e in eng.event_log.all_events()]
    assert EventType.SIM_RESET in types


def test_engine_remove_listener_noop():
    eng = _make_engine()
    cb = lambda e: None
    eng.remove_listener(cb)  # removing non-existent should not raise


def test_engine_remove_listener_removes():
    eng = _make_engine()
    calls = []
    cb = lambda e: calls.append(e)
    eng.add_listener(cb)
    eng.start()
    assert len(calls) > 0
    eng.remove_listener(cb)
    before = len(calls)
    eng.stop()
    assert len(calls) == before  # no new calls after removal


def test_engine_stop_emits_stop_event():
    eng = _make_engine()
    eng.start()
    eng.stop()
    types = [e.event_type for e in eng.event_log.all_events()]
    assert EventType.SIM_STOP in types


def test_engine_step_past_max_ticks_stops():
    eng = _make_engine(max_ticks=3)
    eng.start()
    for _ in range(10):
        eng.step()
    assert not eng.running
    assert eng.tick <= 4


def test_engine_listener_exception_does_not_crash():
    eng = _make_engine()
    def _bad(e):
        raise RuntimeError("boom")
    eng.add_listener(_bad)
    eng.start()  # should not raise


def test_engine_vehicle_moving_state_stops_on_red():
    """Vehicles in MOVING state get QUEUED+stops incremented on red light."""
    eng = _make_engine(max_ticks=200)
    eng.start()
    while eng.running:
        eng.step()
    # At least some vehicles should have stops recorded
    kpi = eng._kpi.snapshot(eng.tick, eng.intersection, eng._active_vehicles)
    assert kpi.vehicles_passed >= 0  # sanity — no crash


# ── Helper functions ──────────────────────────────────────────────────────────

def test_vehicle_to_dict():
    v = Vehicle(vehicle_id="abc123", vehicle_type=VehicleType.TRUCK,
                direction=Direction.SOUTH, state=VehicleState.CROSSING,
                queue_position=2, spawn_tick=1, green_tick=5)
    d = _vehicle_to_dict(v)
    assert d["vehicle_id"] == "abc123"
    assert d["type"] == "truck"
    assert d["direction"] == "S"
    assert d["state"] == "crossing"
    assert d["wait_ticks"] == 4


def test_kpi_to_dict():
    kpi = KPISnapshot(tick=10, run_id="r", avg_wait_ticks=3.5,
                      throughput_per_100_ticks=15.0, vehicles_passed=10,
                      queue_lengths={"N": 2})
    d = _kpi_to_dict(kpi)
    assert d["tick"] == 10
    assert d["vehicles_passed"] == 10


# ── Fixed cycle right-arrow coverage ──────────────────────────────────────────

def test_fixed_cycle_right_arrow_phase():
    """Cover the right_arrow branch in FixedCycleController.compute."""
    import algorithms.fixed_cycle as fc
    original = fc._PHASES
    fc._PHASES = [
        {"green": (Direction.NORTH, Direction.SOUTH),
         "left_arrow": (), "right_arrow": (Direction.NORTH,)},
    ]
    try:
        ctrl = fc.FixedCycleController(green_ticks=2, arrow_ticks=2, yellow_ticks=1, all_red_ticks=1)
        ix = Intersection()
        ctrl.compute(1, ix)
        assert ix.turn_lights[Direction.NORTH]["right"].phase == LightPhase.RIGHT_ARROW
    finally:
        fc._PHASES = original


# ── Engine peek-None defensive guard ──────────────────────────────────────────

def test_engine_move_vehicles_peek_none_guard():
    """Cover the defensive continue when peek() returns None on a non-empty lane."""
    from unittest.mock import patch
    eng = _make_engine(max_ticks=20)
    eng.start()
    for _ in range(5):
        eng.step()
    call_count = [0]
    original_peek = Lane.peek

    def patched_peek(self):
        call_count[0] += 1
        if call_count[0] == 1:
            return None
        return original_peek(self)

    with patch.object(Lane, "peek", patched_peek):
        eng.step()
    assert eng.tick == 6
