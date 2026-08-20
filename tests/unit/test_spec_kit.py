"""Unit tests for the spec kit module."""

from __future__ import annotations

import pytest

from algorithms import discover
from algorithms.switcher import AlgorithmSwitcher
from safety.checker import SafetyChecker
from sim.engine import SimConfig, SimEngine
from sim.enums import Direction
from sim.events import KPISnapshot
from sim.intersection import Intersection
from specs.contracts import ContractViolation, InvariantChecker, postcondition, precondition
from specs.loader import discover_specs, list_spec_files, load_spec
from specs.runner import (
    SpecResult,
    _build_config,
    _compile_check,
    _evaluate_assertion,
    run_scenario,
    run_spec_file,
)
from specs.schema import Assertion, ContractSpec, InvariantSpec, ScenarioSpec, SpecFile

discover()


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_engine(max_ticks: int = 10, seed: int = 0) -> SimEngine:
    cfg = SimConfig(seed=seed, max_ticks=max_ticks, algorithm="fixed_cycle")
    eng = SimEngine(cfg, Intersection(), AlgorithmSwitcher("fixed_cycle"), SafetyChecker())
    eng.start()
    while eng.running:
        eng.step()
    return eng


def _make_kpi(**overrides: object) -> KPISnapshot:
    defaults: dict = dict(
        tick=100,
        run_id="t",
        avg_wait_ticks=5.0,
        max_wait_ticks=12,
        throughput_per_100_ticks=3.0,
        total_stops=4,
        pct_null_control=0.0,
        vehicles_passed=10,
        vehicles_in_system=2,
    )
    defaults.update(overrides)
    return KPISnapshot(**defaults)


# ── Schema: Assertion ────────────────────────────────────────────────────────


def test_assertion_from_dict_full():
    a = Assertion.from_dict(
        {
            "type": "kpi",
            "field": "avg_wait_ticks",
            "operator": "lt",
            "value": 10,
            "event_type": "x",
            "payload_match": {"k": 1},
        }
    )
    assert a.type == "kpi"
    assert a.field_name == "avg_wait_ticks"
    assert a.operator == "lt"


def test_assertion_from_dict_minimal():
    a = Assertion.from_dict({"type": "state"})
    assert a.operator == "eq"
    assert a.field_name is None


@pytest.mark.parametrize(
    "op,a,b,expected",
    [
        ("eq", 5, 5, True),
        ("eq", 5, 6, False),
        ("ne", 5, 6, True),
        ("ne", 5, 5, False),
        ("gt", 6, 5, True),
        ("gt", 5, 5, False),
        ("lt", 4, 5, True),
        ("lt", 5, 5, False),
        ("gte", 5, 5, True),
        ("gte", 4, 5, False),
        ("lte", 5, 5, True),
        ("lte", 6, 5, False),
    ],
)
def test_assertion_evaluate(op, a, b, expected):
    assert Assertion(type="kpi", operator=op, value=b).evaluate(a) is expected


def test_assertion_evaluate_unknown_operator():
    with pytest.raises(ValueError, match="Unknown operator"):
        Assertion(type="kpi", operator="bad", value=0).evaluate(1)


# ── Schema: ScenarioSpec ─────────────────────────────────────────────────────


def test_scenario_from_dict_with_assertions():
    s = ScenarioSpec.from_dict(
        {
            "name": "s1",
            "description": "d",
            "config": {"seed": 1},
            "assertions": [
                {"type": "kpi", "field": "vehicles_passed", "operator": "gt", "value": 0}
            ],
        }
    )
    assert s.name == "s1"
    assert len(s.assertions) == 1


def test_scenario_from_dict_defaults():
    s = ScenarioSpec.from_dict({"name": "s2"})
    assert s.assertions == []
    assert s.config == {}


# ── Schema: InvariantSpec ────────────────────────────────────────────────────


def test_invariant_from_dict():
    i = InvariantSpec.from_dict({"name": "inv", "check": "engine.tick >= 0", "scope": "always"})
    assert i.scope == "always"
    assert i.check == "engine.tick >= 0"


def test_invariant_from_dict_defaults():
    i = InvariantSpec.from_dict({"name": "inv2"})
    assert i.scope == "always"
    assert i.check == ""


# ── Schema: ContractSpec ─────────────────────────────────────────────────────


def test_contract_from_dict():
    c = ContractSpec.from_dict(
        {
            "name": "c1",
            "target": "SimEngine.step",
            "precondition": "self.running",
            "postcondition": "result is not None",
        }
    )
    assert c.target == "SimEngine.step"
    assert c.precondition == "self.running"


def test_contract_from_dict_defaults():
    c = ContractSpec.from_dict({"name": "c2"})
    assert c.target == ""
    assert c.precondition is None


# ── Schema: SpecFile ─────────────────────────────────────────────────────────


def test_spec_file_from_dict_full():
    sf = SpecFile.from_dict(
        {
            "spec_version": "2.0",
            "module": "sim",
            "description": "d",
            "scenarios": [{"name": "s"}],
            "invariants": [{"name": "i", "check": "True"}],
            "contracts": [{"name": "c"}],
        }
    )
    assert sf.spec_version == "2.0"
    assert len(sf.scenarios) == 1
    assert len(sf.invariants) == 1
    assert len(sf.contracts) == 1


def test_spec_file_from_dict_empty():
    sf = SpecFile.from_dict({})
    assert sf.scenarios == []
    assert sf.module == ""


# ── Contracts: ContractViolation ─────────────────────────────────────────────


def test_contract_violation_message():
    exc = ContractViolation("precondition", "my_fn", "bad state")
    assert "precondition" in str(exc)
    assert exc.kind == "precondition"
    assert exc.name == "my_fn"


# ── Contracts: precondition ──────────────────────────────────────────────────


def test_precondition_passes():
    @precondition(lambda x: x > 0, name="positive")
    def inc(x):
        return x + 1

    assert inc(1) == 2


def test_precondition_fails():
    @precondition(lambda x: x > 0, name="positive")
    def inc(x):
        return x + 1

    with pytest.raises(ContractViolation, match="precondition"):
        inc(-1)


def test_precondition_default_name():
    @precondition(lambda x: x > 0)
    def my_func(x):
        return x

    with pytest.raises(ContractViolation, match="my_func"):
        my_func(0)


# ── Contracts: postcondition ─────────────────────────────────────────────────


def test_postcondition_passes():
    @postcondition(lambda result, x: result > x, name="increases")
    def inc(x):
        return x + 1

    assert inc(5) == 6


def test_postcondition_fails():
    @postcondition(lambda result, x: result > x, name="increases")
    def noop(x):
        return x

    with pytest.raises(ContractViolation, match="postcondition"):
        noop(5)


def test_postcondition_default_name():
    @postcondition(lambda result, x: result > 0)
    def my_func(x):
        return x

    with pytest.raises(ContractViolation, match="my_func"):
        my_func(0)


# ── Contracts: InvariantChecker ──────────────────────────────────────────────


def test_invariant_checker_passes():
    ic = InvariantChecker()
    ic.add("positive", lambda val=0, **_: val > 0)
    violations = ic.check(val=5)
    assert violations == []


def test_invariant_checker_fails():
    ic = InvariantChecker()
    ic.add("positive", lambda val=0, **_: val > 0)
    violations = ic.check(val=-1)
    assert len(violations) == 1
    assert violations[0]["name"] == "positive"


def test_invariant_checker_exception():
    ic = InvariantChecker()
    ic.add("boom", lambda **_: 1 / 0)
    violations = ic.check()
    assert len(violations) == 1
    assert "division by zero" in violations[0]["error"]


def test_invariant_checker_accumulates():
    ic = InvariantChecker()
    ic.add("neg", lambda val=0, **_: val < 0)
    ic.check(val=1)
    ic.check(val=2)
    assert len(ic.all_violations) == 2


def test_invariant_checker_clear():
    ic = InvariantChecker()
    ic.add("neg", lambda val=0, **_: val < 0)
    ic.check(val=1)
    assert len(ic.all_violations) == 1
    ic.clear()
    assert ic.all_violations == []


# ── Loader ───────────────────────────────────────────────────────────────────


def test_load_spec_valid(tmp_path):
    p = tmp_path / "test.spec.yaml"
    p.write_text("spec_version: '1.0'\nmodule: sim\nscenarios: []\n")
    sf = load_spec(p)
    assert sf.module == "sim"


def test_load_spec_invalid_yaml(tmp_path):
    p = tmp_path / "bad.spec.yaml"
    p.write_text("just a string\n")
    with pytest.raises(ValueError, match="YAML mapping"):
        load_spec(p)


def test_discover_specs_default():
    specs = discover_specs()
    assert len(specs) >= 3


def test_discover_specs_custom_root(tmp_path):
    (tmp_path / "a.spec.yaml").write_text("module: a\n")
    specs = discover_specs(tmp_path)
    assert len(specs) == 1


def test_list_spec_files_default():
    paths = list_spec_files()
    assert all(p.suffix == ".yaml" for p in paths)


def test_list_spec_files_custom_root(tmp_path):
    (tmp_path / "b.spec.yaml").write_text("module: b\n")
    paths = list_spec_files(tmp_path)
    assert len(paths) == 1


# ── Runner: _build_config ────────────────────────────────────────────────────


def test_build_config_basic():
    cfg = _build_config({"seed": 99, "max_ticks": 50, "algorithm": "fixed_cycle"})
    assert cfg.seed == 99
    assert cfg.max_ticks == 50


def test_build_config_default_max_ticks():
    cfg = _build_config({"seed": 1})
    assert cfg.max_ticks == 1000


def test_build_config_with_arrivals():
    cfg = _build_config(
        {
            "seed": 0,
            "max_ticks": 10,
            "arrivals": {"N": {"mean_interarrival_ticks": 5.0}},
        }
    )
    north_cfg = next(a for a in cfg.arrival_configs if a.direction == Direction.NORTH)
    assert north_cfg.mean_interarrival_ticks == 5.0


def test_build_config_ignores_unknown_keys():
    cfg = _build_config({"seed": 1, "max_ticks": 10, "unknown_key": "ignored"})
    assert cfg.seed == 1


# ── Runner: _evaluate_assertion ──────────────────────────────────────────────


def test_eval_kpi_passes():
    engine = _make_engine()
    kpi = _make_kpi(vehicles_passed=10)
    a = Assertion(type="kpi", field_name="vehicles_passed", operator="gte", value=5)
    assert _evaluate_assertion(a, engine, kpi) is None


def test_eval_kpi_fails():
    engine = _make_engine()
    kpi = _make_kpi(vehicles_passed=2)
    a = Assertion(type="kpi", field_name="vehicles_passed", operator="gt", value=100)
    assert "expected gt" in _evaluate_assertion(a, engine, kpi)


def test_eval_kpi_missing_field_name():
    engine = _make_engine()
    kpi = _make_kpi()
    a = Assertion(type="kpi")
    assert _evaluate_assertion(a, engine, kpi) == "kpi assertion requires 'field'"


def test_eval_kpi_field_not_found():
    engine = _make_engine()
    kpi = _make_kpi()
    a = Assertion(type="kpi", field_name="nonexistent", operator="eq", value=0)
    assert "not found" in _evaluate_assertion(a, engine, kpi)


def test_eval_event_count_passes():
    engine = _make_engine(max_ticks=50)
    kpi = _make_kpi()
    a = Assertion(type="event_count", event_type="light_change", operator="gt", value=0)
    assert _evaluate_assertion(a, engine, kpi) is None


def test_eval_event_count_fails():
    engine = _make_engine(max_ticks=5)
    kpi = _make_kpi()
    a = Assertion(type="event_count", event_type="vehicle_exit", operator="gt", value=9999)
    assert "expected gt" in _evaluate_assertion(a, engine, kpi)


def test_eval_event_count_missing_event_type():
    engine = _make_engine()
    kpi = _make_kpi()
    a = Assertion(type="event_count")
    assert "requires 'event_type'" in _evaluate_assertion(a, engine, kpi)


def test_eval_event_count_with_payload_match():
    engine = _make_engine(max_ticks=50)
    kpi = _make_kpi()
    a = Assertion(
        type="event_count",
        event_type="light_change",
        operator="gte",
        value=0,
        payload_match={"direction": "N"},
    )
    assert _evaluate_assertion(a, engine, kpi) is None


def test_eval_event_exists_found():
    engine = _make_engine(max_ticks=50)
    kpi = _make_kpi()
    a = Assertion(type="event_exists", event_type="sim_start")
    assert _evaluate_assertion(a, engine, kpi) is None


def test_eval_event_exists_not_found():
    engine = _make_engine(max_ticks=5)
    kpi = _make_kpi()
    a = Assertion(type="event_exists", event_type="algorithm_switch")
    assert "No events" in _evaluate_assertion(a, engine, kpi)


def test_eval_event_exists_missing_event_type():
    engine = _make_engine()
    kpi = _make_kpi()
    a = Assertion(type="event_exists")
    assert "requires 'event_type'" in _evaluate_assertion(a, engine, kpi)


def test_eval_event_exists_with_payload_match():
    engine = _make_engine(max_ticks=50)
    kpi = _make_kpi()
    a = Assertion(
        type="event_exists",
        event_type="light_change",
        payload_match={"to_phase": "impossible_value_xyz"},
    )
    assert "No events" in _evaluate_assertion(a, engine, kpi)


def test_eval_no_event_passes():
    engine = _make_engine(max_ticks=5)
    kpi = _make_kpi()
    a = Assertion(type="no_event", event_type="algorithm_switch")
    assert _evaluate_assertion(a, engine, kpi) is None


def test_eval_no_event_fails():
    engine = _make_engine(max_ticks=50)
    kpi = _make_kpi()
    a = Assertion(type="no_event", event_type="sim_start")
    assert "Expected no events" in _evaluate_assertion(a, engine, kpi)


def test_eval_no_event_missing_event_type():
    engine = _make_engine()
    kpi = _make_kpi()
    a = Assertion(type="no_event")
    assert "requires 'event_type'" in _evaluate_assertion(a, engine, kpi)


def test_eval_no_event_with_payload_match():
    engine = _make_engine(max_ticks=50)
    kpi = _make_kpi()
    a = Assertion(
        type="no_event",
        event_type="light_change",
        payload_match={"to_phase": "impossible_value_xyz"},
    )
    assert _evaluate_assertion(a, engine, kpi) is None


def test_eval_state_passes():
    engine = _make_engine()
    kpi = _make_kpi()
    a = Assertion(type="state", field_name="running", operator="eq", value=False)
    assert _evaluate_assertion(a, engine, kpi) is None


def test_eval_state_fails():
    engine = _make_engine()
    kpi = _make_kpi()
    a = Assertion(type="state", field_name="tick", operator="gt", value=9999)
    assert "expected gt" in _evaluate_assertion(a, engine, kpi)


def test_eval_state_missing_field_name():
    engine = _make_engine()
    kpi = _make_kpi()
    a = Assertion(type="state")
    assert "requires 'field'" in _evaluate_assertion(a, engine, kpi)


def test_eval_state_field_not_found():
    engine = _make_engine()
    kpi = _make_kpi()
    a = Assertion(type="state", field_name="nonexistent_attr", operator="eq", value=0)
    assert "not found" in _evaluate_assertion(a, engine, kpi)


def test_eval_unknown_type():
    engine = _make_engine()
    kpi = _make_kpi()
    a = Assertion(type="bogus")
    assert "Unknown assertion type" in _evaluate_assertion(a, engine, kpi)


# ── Runner: _compile_check ───────────────────────────────────────────────────


def test_compile_check_passes():
    fn = _compile_check("engine.tick >= 0")
    engine = _make_engine()
    assert fn(engine=engine) is True


def test_compile_check_fails():
    fn = _compile_check("engine.tick < 0")
    engine = _make_engine()
    assert fn(engine=engine) is False


def test_compile_check_with_direction():
    fn = _compile_check("len(intersection.lights) == len(list(Direction))")
    engine = _make_engine()
    assert fn(engine=engine) is True


# ── Runner: run_scenario ─────────────────────────────────────────────────────


def test_run_scenario_passes():
    s = ScenarioSpec(
        name="basic",
        config={"seed": 0, "max_ticks": 20},
        assertions=[Assertion(type="state", field_name="running", operator="eq", value=False)],
    )
    result = run_scenario(s)
    assert result.passed is True


def test_run_scenario_with_passing_invariant():
    s = ScenarioSpec(name="inv_ok", config={"seed": 0, "max_ticks": 20}, assertions=[])
    inv = [InvariantSpec(name="tick_ok", check="engine.tick >= 0", scope="always")]
    result = run_scenario(s, invariants=inv)
    assert result.passed is True


def test_run_scenario_with_failing_invariant():
    s = ScenarioSpec(name="inv_fail", config={"seed": 0, "max_ticks": 20}, assertions=[])
    inv = [InvariantSpec(name="impossible", check="engine.tick < 0", scope="always")]
    result = run_scenario(s, invariants=inv)
    assert result.passed is False
    assert any("impossible" in f for f in result.failures)


def test_run_scenario_with_post_run_invariant():
    s = ScenarioSpec(name="post", config={"seed": 0, "max_ticks": 10}, assertions=[])
    inv = [InvariantSpec(name="ran", check="engine.tick > 0", scope="post_run")]
    result = run_scenario(s, invariants=inv)
    assert result.passed is True


def test_run_scenario_with_failing_post_run_invariant():
    s = ScenarioSpec(name="post_fail", config={"seed": 0, "max_ticks": 10}, assertions=[])
    inv = [InvariantSpec(name="never", check="engine.tick < 0", scope="post_run")]
    result = run_scenario(s, invariants=inv)
    assert result.passed is False


def test_run_scenario_assertion_failure():
    s = ScenarioSpec(
        name="assert_fail",
        config={"seed": 0, "max_ticks": 10},
        assertions=[
            Assertion(type="kpi", field_name="vehicles_passed", operator="gt", value=999999)
        ],
    )
    result = run_scenario(s)
    assert result.passed is False


# ── Runner: run_spec_file ────────────────────────────────────────────────────


def test_run_spec_file_all_pass():
    sf = SpecFile(
        module="test",
        scenarios=[
            ScenarioSpec(
                name="a",
                config={"seed": 0, "max_ticks": 10},
                assertions=[
                    Assertion(type="state", field_name="running", operator="eq", value=False)
                ],
            ),
            ScenarioSpec(
                name="b",
                config={"seed": 1, "max_ticks": 10},
                assertions=[
                    Assertion(type="state", field_name="running", operator="eq", value=False)
                ],
            ),
        ],
    )
    results = run_spec_file(sf)
    assert len(results) == 2
    assert all(r.passed for r in results)


# ── Runner: SpecResult ───────────────────────────────────────────────────────


def test_spec_result_fail():
    r = SpecResult("test")
    assert r.passed is True
    r.fail("oh no")
    assert r.passed is False
    assert "oh no" in r.failures


# ── Integration: discover_specs + run ────────────────────────────────────────


def test_all_bundled_specs_pass():
    for sf in discover_specs():
        for result in run_spec_file(sf):
            assert result.passed is True, f"{result.spec_name}: {result.failures}"
