"""Data models for spec-driven development YAML files."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Assertion:
    """A single assertion to verify after running a scenario."""

    type: str
    operator: str = "eq"
    value: Any = None
    field_name: str | None = None
    event_type: str | None = None
    payload_match: dict[str, Any] | None = None

    _OPERATORS: dict[str, Any] = field(default=None, init=False, repr=False)

    def evaluate(self, actual: Any) -> bool:
        """Check if actual value satisfies the operator constraint against expected value."""
        ops = {
            "eq": lambda a, b: a == b,
            "ne": lambda a, b: a != b,
            "gt": lambda a, b: a > b,
            "lt": lambda a, b: a < b,
            "gte": lambda a, b: a >= b,
            "lte": lambda a, b: a <= b,
        }
        op_fn = ops.get(self.operator)
        if op_fn is None:
            raise ValueError(f"Unknown operator: {self.operator}")
        return op_fn(actual, self.value)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Assertion:
        return cls(
            type=data["type"],
            operator=data.get("operator", "eq"),
            value=data.get("value"),
            field_name=data.get("field"),
            event_type=data.get("event_type"),
            payload_match=data.get("payload_match"),
        )


@dataclass
class ScenarioSpec:
    """A simulation scenario with config and expected outcomes."""

    name: str
    description: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    assertions: list[Assertion] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScenarioSpec:
        assertions = [Assertion.from_dict(a) for a in data.get("assertions", [])]
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            config=data.get("config", {}),
            assertions=assertions,
        )


@dataclass
class InvariantSpec:
    """A formal invariant checked during simulation execution."""

    name: str
    description: str = ""
    check: str = ""
    scope: str = "always"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InvariantSpec:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            check=data.get("check", ""),
            scope=data.get("scope", "always"),
        )


@dataclass
class ContractSpec:
    """Pre/post condition contract on a function or method."""

    name: str
    target: str = ""
    precondition: str | None = None
    postcondition: str | None = None
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContractSpec:
        return cls(
            name=data["name"],
            target=data.get("target", ""),
            precondition=data.get("precondition"),
            postcondition=data.get("postcondition"),
            description=data.get("description", ""),
        )


@dataclass
class SpecFile:
    """Root model for a spec YAML file."""

    spec_version: str = "1.0"
    module: str = ""
    description: str = ""
    scenarios: list[ScenarioSpec] = field(default_factory=list)
    invariants: list[InvariantSpec] = field(default_factory=list)
    contracts: list[ContractSpec] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpecFile:
        return cls(
            spec_version=data.get("spec_version", "1.0"),
            module=data.get("module", ""),
            description=data.get("description", ""),
            scenarios=[ScenarioSpec.from_dict(s) for s in data.get("scenarios", [])],
            invariants=[InvariantSpec.from_dict(i) for i in data.get("invariants", [])],
            contracts=[ContractSpec.from_dict(c) for c in data.get("contracts", [])],
        )
