"""Execute spec scenarios, check invariants, and evaluate assertions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from algorithms import discover
from algorithms.switcher import AlgorithmSwitcher
from safety.checker import SafetyChecker
from sim.engine import SimConfig, SimEngine
from sim.enums import Direction, EventType, LightPhase
from sim.events import KPISnapshot
from sim.generator import ArrivalConfig
from sim.intersection import Intersection
from specs.contracts import InvariantChecker
from specs.schema import Assertion, InvariantSpec, ScenarioSpec, SpecFile

_SAFE_BUILTINS: dict[str, Any] = {
    "True": True,
    "False": False,
    "None": None,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "sum": sum,
}

_MAX_TICKS_DEFAULT = 1000


@dataclass
class SpecResult:
    """Outcome of running a single spec scenario."""

    spec_name: str
    passed: bool = True
    failures: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.passed = False
        self.failures.append(message)


def _build_config(config_dict: dict[str, Any]) -> SimConfig:
    """Translate a spec config mapping into a SimConfig."""
    config_dict = dict(config_dict)
    arrival_overrides = config_dict.pop("arrivals", None)

    if "max_ticks" not in config_dict:
        config_dict["max_ticks"] = _MAX_TICKS_DEFAULT

    valid_keys = set(SimConfig.__dataclass_fields__)
    filtered = {k: v for k, v in config_dict.items() if k in valid_keys}
    cfg = SimConfig(**filtered)

    if arrival_overrides:
        configs = []
        for d in Direction:
            override = arrival_overrides.get(d.value, {})
            configs.append(ArrivalConfig(direction=d, **override))
        cfg.arrival_configs = configs

    return cfg


def _get_kpi(engine: SimEngine) -> KPISnapshot:
    return engine._kpi.snapshot(engine.tick, engine.intersection, engine._active_vehicles)


def _evaluate_assertion(assertion: Assertion, engine: SimEngine, kpi: KPISnapshot) -> str | None:
    """Evaluate one assertion. Returns a failure message or ``None`` on success."""
    if assertion.type == "kpi":
        if assertion.field_name is None:
            return "kpi assertion requires 'field'"
        actual = getattr(kpi, assertion.field_name, None)
        if actual is None:
            return f"KPI field '{assertion.field_name}' not found"
        if not assertion.evaluate(actual):
            return (
                f"KPI {assertion.field_name}: expected {assertion.operator} "
                f"{assertion.value}, got {actual}"
            )

    elif assertion.type == "event_count":
        if assertion.event_type is None:
            return "event_count assertion requires 'event_type'"
        etype = EventType(assertion.event_type)
        events = engine.event_log.events_of_type(etype)
        if assertion.payload_match:
            events = [
                e
                for e in events
                if all(e.payload.get(k) == v for k, v in assertion.payload_match.items())
            ]
        count = len(events)
        if not assertion.evaluate(count):
            return (
                f"Event count {assertion.event_type}: expected {assertion.operator} "
                f"{assertion.value}, got {count}"
            )

    elif assertion.type == "event_exists":
        if assertion.event_type is None:
            return "event_exists assertion requires 'event_type'"
        etype = EventType(assertion.event_type)
        events = engine.event_log.events_of_type(etype)
        if assertion.payload_match:
            events = [
                e
                for e in events
                if all(e.payload.get(k) == v for k, v in assertion.payload_match.items())
            ]
        if not events:
            return f"No events of type {assertion.event_type} found"

    elif assertion.type == "no_event":
        if assertion.event_type is None:
            return "no_event assertion requires 'event_type'"
        etype = EventType(assertion.event_type)
        events = engine.event_log.events_of_type(etype)
        if assertion.payload_match:
            events = [
                e
                for e in events
                if all(e.payload.get(k) == v for k, v in assertion.payload_match.items())
            ]
        if events:
            return f"Expected no events of type {assertion.event_type}, found {len(events)}"

    elif assertion.type == "state":
        if assertion.field_name is None:
            return "state assertion requires 'field'"
        actual = getattr(engine, assertion.field_name, None)
        if actual is None:
            return f"Engine field '{assertion.field_name}' not found"
        if not assertion.evaluate(actual):
            return (
                f"State {assertion.field_name}: expected {assertion.operator} "
                f"{assertion.value}, got {actual}"
            )

    else:
        return f"Unknown assertion type: {assertion.type}"

    return None


def _compile_check(expression: str) -> Callable[..., bool]:
    """Compile a Python expression into a callable ``(**ctx) -> bool``."""
    code = compile(expression, "<invariant>", "eval")

    def check_fn(**ctx: Any) -> bool:
        engine = ctx["engine"]
        local_vars: dict[str, Any] = {
            "__builtins__": _SAFE_BUILTINS,
            "engine": engine,
            "intersection": engine.intersection,
            "Direction": Direction,
            "LightPhase": LightPhase,
        }
        return bool(eval(code, local_vars))  # noqa: S307 – sandboxed builtins

    return check_fn


def run_scenario(
    scenario: ScenarioSpec, invariants: list[InvariantSpec] | None = None
) -> SpecResult:
    """Run a single spec scenario and verify assertions + invariants."""
    discover()
    result = SpecResult(scenario.name)
    config = _build_config(scenario.config)

    ix = Intersection()
    switcher = AlgorithmSwitcher(config.algorithm)
    safety = SafetyChecker()
    engine = SimEngine(config, ix, switcher, safety)

    # Build per-scope invariant checkers
    tick_checker = InvariantChecker()
    post_checker = InvariantChecker()
    for inv in invariants or []:
        fn = _compile_check(inv.check)
        if inv.scope in ("always", "when_running"):
            tick_checker.add(inv.name, fn)
        if inv.scope in ("always", "post_run"):
            post_checker.add(inv.name, fn)

    engine.start()
    while engine.running:
        engine.step()
        violations = tick_checker.check(engine=engine)
        if violations:
            for v in violations:
                result.fail(f"Invariant '{v['name']}': {v['error']} (tick {engine.tick})")
            break

    post_violations = post_checker.check(engine=engine)
    for v in post_violations:
        result.fail(f"Post-run invariant '{v['name']}': {v['error']}")

    kpi = _get_kpi(engine)
    for assertion in scenario.assertions:
        failure = _evaluate_assertion(assertion, engine, kpi)
        if failure:
            result.fail(failure)

    return result


def run_spec_file(spec_file: SpecFile) -> list[SpecResult]:
    """Run every scenario in a spec file, sharing its invariants."""
    return [run_scenario(s, spec_file.invariants) for s in spec_file.scenarios]
