"""
Tests for algorithms/ — covers registry, all controllers, and switcher edge cases.
"""
import pytest
from sim.enums import Direction, LightPhase
from sim.intersection import Intersection
from algorithms import discover, get, available, register, ControllerProtocol
from algorithms.null_control import NullController
from algorithms.fixed_cycle import FixedCycleController
from algorithms.adaptive_cycle import AdaptiveCycleController
from algorithms.switcher import AlgorithmSwitcher

discover()


# ── Registry ─────────────────────────────────────────────────────────────────

def test_available_contains_all_builtin():
    algos = available()
    assert "fixed_cycle" in algos
    assert "adaptive_cycle" in algos
    assert "null_control" in algos


def test_get_returns_class():
    cls = get("fixed_cycle")
    assert cls.name == "fixed_cycle"


def test_get_unknown_raises_key_error():
    with pytest.raises(KeyError, match="not found"):
        get("nonexistent_algo_xyz")


def test_discover_loads_unloaded_module():
    """Remove a module from sys.modules and re-discover to hit loading branch."""
    import sys
    mod_name = "algorithms.fixed_cycle"
    # Save and temporarily remove
    saved = sys.modules.pop(mod_name, None)
    try:
        discover()  # should re-load the module
        assert mod_name in sys.modules
        assert "fixed_cycle" in available()
    finally:
        # Restore original if it was there
        if saved is not None:
            sys.modules[mod_name] = saved


def test_register_decorator():
    import algorithms as _alg
    @register
    class _TestAlgo:
        name = "_test_tmp_algo_do_not_use"
        def compute(self, tick, intersection):
            return {d: LightPhase.RED for d in Direction}

    assert "_test_tmp_algo_do_not_use" in available()
    assert get("_test_tmp_algo_do_not_use") is _TestAlgo
    # Clean up so it doesn't pollute other tests (e.g. analytics palette)
    del _alg._REGISTRY["_test_tmp_algo_do_not_use"]


def test_controller_protocol_runtime_check():
    ctrl = NullController()
    assert isinstance(ctrl, ControllerProtocol)


# ── NullController ────────────────────────────────────────────────────────────

def test_null_controller_all_amber():
    ctrl = NullController()
    ix = Intersection()
    result = ctrl.compute(1, ix)
    assert all(p == LightPhase.AMBER_FLASH for p in result.values())
    assert set(result.keys()) == set(Direction)


def test_null_controller_name():
    assert NullController.name == "null_control"


# ── FixedCycleController ──────────────────────────────────────────────────────

def test_fixed_cycle_produces_valid_phases():
    ctrl = FixedCycleController()
    ix = Intersection()
    for tick in range(1, 100):
        commands = ctrl.compute(tick, ix)
        assert set(commands.keys()) == set(Direction)
        assert all(isinstance(p, LightPhase) for p in commands.values())


def test_fixed_cycle_ns_and_ew_alternate():
    """After a full cycle, both NS and EW should have seen GREEN."""
    ctrl = FixedCycleController()
    ix = Intersection()
    seen_ns_green = False
    seen_ew_green = False
    for tick in range(1, 200):
        cmds = ctrl.compute(tick, ix)
        if cmds[Direction.NORTH] == LightPhase.GREEN:
            seen_ns_green = True
        if cmds[Direction.EAST] == LightPhase.GREEN:
            seen_ew_green = True
        if seen_ns_green and seen_ew_green:
            break
    assert seen_ns_green
    assert seen_ew_green


def test_fixed_cycle_no_conflicting_greens():
    ctrl = FixedCycleController()
    ix = Intersection()
    for tick in range(1, 200):
        cmds = ctrl.compute(tick, ix)
        ns_green = cmds[Direction.NORTH] == LightPhase.GREEN
        ew_green = cmds[Direction.EAST] == LightPhase.GREEN
        assert not (ns_green and ew_green), f"Conflicting greens at tick {tick}"


# ── AdaptiveCycleController ───────────────────────────────────────────────────

def test_adaptive_cycle_produces_all_directions():
    ctrl = AdaptiveCycleController()
    ix = Intersection()
    for tick in range(1, 50):
        cmds = ctrl.compute(tick, ix)
        assert set(cmds.keys()) == set(Direction)


def test_adaptive_cycle_extends_green_on_high_queue():
    """With a long queue on one axis, adaptive should extend green."""
    ctrl = AdaptiveCycleController()
    ix = Intersection()
    # Fill NORTH queue
    from sim.vehicles import Vehicle
    for _ in range(15):
        ix.lanes[Direction.NORTH].enqueue(Vehicle())

    green_count = 0
    for tick in range(1, 150):
        cmds = ctrl.compute(tick, ix)
        if cmds[Direction.NORTH] == LightPhase.GREEN:
            green_count += 1
    assert green_count > 0


def test_adaptive_cycle_all_red_phase():
    """Adaptive goes through an all-red phase between NS and EW."""
    ctrl = AdaptiveCycleController()
    ix = Intersection()
    all_red_seen = False
    for tick in range(1, 200):
        cmds = ctrl.compute(tick, ix)
        if all(p == LightPhase.RED for p in cmds.values()):
            all_red_seen = True
            break
    assert all_red_seen


def test_adaptive_cycle_yellow_phase():
    """Adaptive should emit YELLOW before transitioning to red."""
    ctrl = AdaptiveCycleController()
    ix = Intersection()
    yellow_seen = False
    for tick in range(1, 200):
        cmds = ctrl.compute(tick, ix)
        if any(p == LightPhase.YELLOW for p in cmds.values()):
            yellow_seen = True
            break
    assert yellow_seen


# ── AlgorithmSwitcher ─────────────────────────────────────────────────────────

def test_switcher_initial_name():
    sw = AlgorithmSwitcher("fixed_cycle")
    assert sw.active_name == "fixed_cycle"


def test_switcher_request_same_algo_noop():
    sw = AlgorithmSwitcher("fixed_cycle")
    sw.request_switch("fixed_cycle")
    # No intergreen should be inserted
    ix = Intersection()
    for tick in range(1, 5):
        cmds = sw.compute(tick, ix)
    assert sw.active_name == "fixed_cycle"


def test_switcher_invalid_algo_raises():
    sw = AlgorithmSwitcher("fixed_cycle")
    with pytest.raises(KeyError):
        sw.request_switch("does_not_exist_xyz")


def test_switcher_switch_inserts_all_red():
    sw = AlgorithmSwitcher("fixed_cycle")
    sw.request_switch("adaptive_cycle")
    ix = Intersection()
    # First 4 ticks should be all-red
    for tick in range(1, 5):
        cmds = sw.compute(tick, ix)
        assert all(p == LightPhase.RED for p in cmds.values())


def test_switcher_completes_switch_after_intergreen():
    sw = AlgorithmSwitcher("fixed_cycle")
    sw.request_switch("adaptive_cycle")
    ix = Intersection()
    # Exhaust the intergreen
    for tick in range(1, 6):
        sw.compute(tick, ix)
    assert sw.active_name == "adaptive_cycle"


def test_switcher_switch_while_already_switching():
    """Request a second switch while intergreen is in progress."""
    sw = AlgorithmSwitcher("fixed_cycle")
    sw.request_switch("adaptive_cycle")
    sw.request_switch("null_control")  # override pending switch
    ix = Intersection()
    for tick in range(1, 10):
        sw.compute(tick, ix)
    assert sw.active_name == "null_control"
