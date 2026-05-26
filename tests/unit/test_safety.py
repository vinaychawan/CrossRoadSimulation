"""Unit tests for safety checker."""
import pytest
from sim.enums import Direction, LightPhase
from sim.intersection import Intersection
from safety.checker import SafetyChecker


def _checker():
    return SafetyChecker(all_red_intergreen_ticks=4)


def _ix():
    return Intersection()


# ── R1: No conflicting greens ─────────────────────────────────────────────

def test_r1_conflicting_greens_overrides():
    checker = _checker()
    ix = _ix()
    commands = {
        Direction.NORTH: LightPhase.GREEN,
        Direction.EAST: LightPhase.GREEN,
        Direction.SOUTH: LightPhase.RED,
        Direction.WEST: LightPhase.RED,
    }
    safe, violations = checker.check(commands, ix)
    assert violations, "R1 should fire"
    assert all(p == LightPhase.AMBER_FLASH for p in safe.values())
    assert any(v["rule"] == "R1_CONFLICTING_GREEN" for v in violations)


def test_r1_ns_ew_valid():
    checker = _checker()
    ix = _ix()
    # NS green + EW red is safe
    commands = {
        Direction.NORTH: LightPhase.GREEN,
        Direction.SOUTH: LightPhase.GREEN,
        Direction.EAST: LightPhase.RED,
        Direction.WEST: LightPhase.RED,
    }
    safe, violations = checker.check(commands, ix)
    assert not violations
    assert safe[Direction.NORTH] == LightPhase.GREEN


# ── R2: RED→GREEN skip ───────────────────────────────────────────────────────

def test_r2_red_to_green_too_soon():
    checker = _checker()
    ix = _ix()
    # First, let N+S go GREEN to register them in the checker's "ever been green" set.
    # At startup R2 does not apply (no previous green phase to clear).
    initial_cmd = {d: LightPhase.RED for d in Direction}
    initial_cmd[Direction.NORTH] = LightPhase.GREEN
    initial_cmd[Direction.SOUTH] = LightPhase.GREEN
    safe0, violations0 = checker.check(initial_cmd, ix)
    assert not violations0  # clean on first activation

    # Now N+S are "ever_been_green". Attempting RED→GREEN again with 0 ticks in red
    # (intersection lights still show RED because we never applied them) should trigger R2.
    commands = {d: LightPhase.RED for d in Direction}
    commands[Direction.NORTH] = LightPhase.GREEN
    commands[Direction.SOUTH] = LightPhase.GREEN
    safe, violations = checker.check(commands, ix)
    assert violations
    assert any(v["rule"] == "R2_RED_TO_GREEN_SKIP" for v in violations)


def test_r2_red_to_green_after_intergreen_ok():
    checker = SafetyChecker(all_red_intergreen_ticks=2)
    ix = _ix()
    # Advance ticks_in_phase past intergreen
    for d in Direction:
        for _ in range(3):
            ix.lights[d].tick()
    commands = {
        Direction.NORTH: LightPhase.GREEN,
        Direction.SOUTH: LightPhase.GREEN,
        Direction.EAST: LightPhase.RED,
        Direction.WEST: LightPhase.RED,
    }
    _, violations = checker.check(commands, ix)
    # R1 won't fire (N+S is fine), R2 won't fire (enough ticks in red)
    r2 = [v for v in violations if v["rule"] == "R2_RED_TO_GREEN_SKIP"]
    assert not r2


def test_intervention_counter_increments():
    checker = _checker()
    ix = _ix()
    bad = {
        Direction.NORTH: LightPhase.GREEN,
        Direction.EAST: LightPhase.GREEN,
        Direction.SOUTH: LightPhase.RED,
        Direction.WEST: LightPhase.RED,
    }
    checker.check(bad, ix)
    checker.check(bad, ix)
    assert checker.total_interventions == 2


def test_violation_explanation_is_human_readable():
    checker = _checker()
    ix = _ix()
    commands = {d: LightPhase.RED for d in Direction}
    commands[Direction.NORTH] = LightPhase.GREEN
    commands[Direction.EAST] = LightPhase.GREEN
    _, violations = checker.check(commands, ix)
    for v in violations:
        assert len(v["explanation"]) > 20
        assert "Rule" in v["explanation"]
