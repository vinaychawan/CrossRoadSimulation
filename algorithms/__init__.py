"""algorithms package – plugin registry."""
from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Protocol, runtime_checkable

from sim.enums import Direction, LightPhase
from sim.intersection import Intersection

logger = logging.getLogger("algorithms")


@runtime_checkable
class ControllerProtocol(Protocol):
    """Interface every algorithm must satisfy."""

    name: str   # unique registry key

    def compute(
        self, tick: int, intersection: Intersection
    ) -> dict[Direction, LightPhase]:
        """Return desired phase for every direction this tick."""
        ...


_REGISTRY: dict[str, type[ControllerProtocol]] = {}


def register(cls: type[ControllerProtocol]) -> type[ControllerProtocol]:
    """Class decorator to register an algorithm."""
    _REGISTRY[cls.name] = cls
    logger.debug("Registered algorithm: %s", cls.name)
    return cls


def get(name: str) -> type[ControllerProtocol]:
    if name not in _REGISTRY:
        raise KeyError(f"Algorithm '{name}' not found. Available: {list(_REGISTRY)}")
    return _REGISTRY[name]


def available() -> list[str]:
    return list(_REGISTRY.keys())


def discover(folder: Path | str | None = None) -> None:
    """
    Dynamically import all *.py files in *folder* so their @register
    decorators fire.  Defaults to the built-in algorithms/ directory.
    """
    if folder is None:
        folder = Path(__file__).parent
    folder = Path(folder)
    for path in sorted(folder.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        module_name = f"algorithms.{path.stem}"
        if module_name in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            logger.debug("Discovered algorithm module: %s", module_name)
