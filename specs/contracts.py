"""Runtime contract decorators and invariant checker for spec-driven development."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any


class ContractViolation(Exception):
    """Raised when a runtime contract (precondition, postcondition, or invariant) is violated."""

    def __init__(self, kind: str, name: str, message: str) -> None:
        self.kind = kind
        self.name = name
        super().__init__(f"{kind} contract '{name}' violated: {message}")


def precondition(pred: Callable[..., bool], name: str = "") -> Callable:
    """Decorator: checks *pred* before the wrapped function executes."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not pred(*args, **kwargs):
                raise ContractViolation("precondition", name or fn.__name__, "check failed")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def postcondition(pred: Callable[..., bool], name: str = "") -> Callable:
    """Decorator: checks *pred* after the wrapped function executes.

    The predicate receives ``(result, *args, **kwargs)`` where *result* is the
    return value of the wrapped call.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = fn(*args, **kwargs)
            if not pred(result, *args, **kwargs):
                raise ContractViolation("postcondition", name or fn.__name__, "check failed")
            return result

        return wrapper

    return decorator


class InvariantChecker:
    """Collects named check functions and evaluates them against context kwargs."""

    def __init__(self) -> None:
        self._invariants: list[tuple[str, Callable[..., bool]]] = []
        self._violations: list[dict[str, str]] = []

    def add(self, name: str, check_fn: Callable[..., bool]) -> None:
        self._invariants.append((name, check_fn))

    def check(self, **context: Any) -> list[dict[str, str]]:
        """Run all registered invariants. Returns list of violation dicts for this call."""
        violations: list[dict[str, str]] = []
        for inv_name, check_fn in self._invariants:
            try:
                passed = check_fn(**context)
            except Exception as exc:
                violations.append({"name": inv_name, "error": str(exc)})
                continue
            if not passed:
                violations.append({"name": inv_name, "error": "invariant check returned False"})
        self._violations.extend(violations)
        return violations

    @property
    def all_violations(self) -> list[dict[str, str]]:
        return list(self._violations)

    def clear(self) -> None:
        self._violations.clear()
