# Crossroads Sim — Agent Instructions

A discrete-time, plugin-based traffic-light simulator with a Flask REST + WebSocket API, SQLAlchemy persistence, and a browser canvas UI.

## Quick Start

```bash
# Create venv and install
make install             # python3 -m venv .venv && pip install -r requirements.txt

# Apply DB schema
make migrate             # alembic upgrade head

# Start the server (http://localhost:8000)
make run                 # python3 -m api.main

# Run tests
make test                # pytest
make test-unit-cov-100   # unit tests + mandatory 100% coverage gate ← required before every commit
make lint                # ruff check
make fmt                 # ruff format
```

**Coverage gate is non-negotiable.** `make test-unit-cov-100` enforces 100% unit coverage across `sim`, `safety`, `algorithms`, `persistence`, `api`. Any new code in those modules requires corresponding tests before pushing.

## Architecture

| Layer | Directory | Responsibility |
|---|---|---|
| Simulation engine | `sim/` | Discrete-time loop, vehicles, lights, intersection, append-only `EventLog`, KPI tracker |
| Algorithms (plugins) | `algorithms/` | Strategy plugins: `fixed_cycle`, `adaptive_cycle`, `null_control`. Register with `@register` decorator |
| Safety | `safety/` | Pre-execution validation: blocks conflicting greens (R1) and RED→GREEN skips (R2) |
| Persistence | `persistence/` | SQLAlchemy 2 ORM (`models.py`), session factory (`database.py`), CRUD helpers (`crud.py`) |
| API | `api/` | Flask + Flask-Sock: REST endpoints, WebSocket broadcast, Bearer token auth, Pydantic schemas |
| Migrations | `migrations/` | Alembic — run `make migrate` after any model change |
| Scenarios | `scenarios/` | Headless demo scripts |
| UI | `ui/static/` | Single-page browser UI (canvas + KPI panel) — served by Flask |

## Key Design Decisions

- **Determinism:** Each run uses a single seeded `random.Random`; seed is persisted in DB. Same seed → identical `EventLog`.
- **Plugin system:** Algorithms use `@register` + `discover()`. New algorithms only need to be placed in `algorithms/` — no import changes required.
- **Safe algorithm switching:** `AlgorithmSwitcher` inserts a 4-tick all-red intergreen before switching. Never switch algorithms by calling the controller directly.
- **Safety layer:** `SafetyChecker` sits between the algorithm and the lights. It intercepts and logs every override. Never bypass it.
- **Event sourcing:** `EventLog` is append-only with SHA-256 checksum — used for regression tests (`tests/unit/test_regression.py`).
- **WebSocket broadcast:** Each connected client gets its own `asyncio.Queue`. Disconnect handling is built in.

## Adding a New Algorithm

```python
# algorithms/my_algorithm.py
from algorithms import register

@register
class MyAlgorithm:
    name = "my_algorithm"
    def compute(self, tick: int, intersection: Intersection) -> dict[Direction, LightPhase]:
        ...
```

No other changes needed — `discover()` auto-loads from the `algorithms/` directory.

## Testing Conventions

- **Unit tests:** `tests/unit/` — one file per module (`test_sim.py`, `test_api.py`, `test_safety.py`, etc.)
- **Property tests:** `tests/property/test_invariants.py` — Hypothesis invariants
- **Regression tests:** `tests/unit/test_regression.py` — verify same seed → same event log
- **Fixtures** (`tests/conftest.py`): `load_algorithms()`, `default_config()` (`seed=0, max_ticks=100`), `engine()`
- **Auth in tests:** Use `HEADERS = {"Authorization": "Bearer dev-token"}` (default dev token from `.env`)
- **Coverage source:** `sim`, `safety`, `algorithms`, `persistence`, `api` (migrations excluded)

See [README.md](README.md) and [REFLECTION.md](REFLECTION.md) for detailed usage and design rationale.

## Environment

Settings are loaded via `python-dotenv` from `.env`. Key vars:

| Variable | Default | Purpose |
|---|---|---|
| `API_TOKEN` | `dev-token` | Bearer token for mutating endpoints |
| `DATABASE_URL` | `sqlite:///./crossroads.db` | SQLAlchemy DB URL |
| `SECRET_KEY` | `change-me-in-production` | Flask secret — **change in production** |
| `DEBUG` | `false` | Debug mode |

## Code Style

- Ruff enforces: `E`, `F`, `I` (sorted imports), `UP`, `B`, `SIM`; line-length = 100
- Full type annotations throughout; use `Protocol` for interfaces
- `from __future__ import annotations` at top of files with forward references
- Module-level docstrings on all `.py` files
- Run `make fmt` before committing to auto-format
