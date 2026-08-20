"""Load and discover YAML spec files."""

from __future__ import annotations

from pathlib import Path

import yaml

from specs.schema import SpecFile

SPEC_DIR = Path(__file__).parent / "definitions"


def load_spec(path: Path | str) -> SpecFile:
    """Load a single ``*.spec.yaml`` file and return a validated SpecFile."""
    path = Path(path)
    with open(path) as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Spec file {path} must contain a YAML mapping, got {type(data).__name__}")
    return SpecFile.from_dict(data)


def discover_specs(root: Path | str | None = None) -> list[SpecFile]:
    """Recursively find and load all ``*.spec.yaml`` files under *root*."""
    root = Path(root) if root else SPEC_DIR
    return [load_spec(p) for p in sorted(root.rglob("*.spec.yaml"))]


def list_spec_files(root: Path | str | None = None) -> list[Path]:
    """Return sorted paths of all ``*.spec.yaml`` files under *root*."""
    root = Path(root) if root else SPEC_DIR
    return sorted(root.rglob("*.spec.yaml"))
