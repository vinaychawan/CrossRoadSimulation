# Crossroads Sim

A production-quality discrete-time traffic-light simulator with:

- **Adaptive + fixed-cycle algorithms** via a plugin registry
- **Safety checker** that enforces no-conflicting-greens, prevents RED→GREEN skips, logs every override
- **WebSocket-streamed** browser UI (canvas + KPI panel) served by FastAPI
- **SQLAlchemy 2 / Alembic** persistence for layouts, scenarios, run history, and recordings
- **Property-based tests** (Hypothesis) + **determinism regression tests**
- **What-if Monte Carlo runner** producing KPI distributions

---

## Quick Start

```bash
# 1. Clone and set up
git clone <repo> crossroads-sim
cd crossroads-sim
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Apply DB migrations
alembic upgrade head

# 3. Start the server
python3 -m api.main              # → http://localhost:8000

# 4. Open browser
open http://localhost:8000
```

**Minimal one-liner (no venv):**
```bash
pip install -r requirements.txt --prefer-binary --break-system-packages
python3 -m api.main
```

---

## Demo Steps

### A. Browser UI demo
1. Open `http://localhost:8000`
2. Click **Create** → **▶ Start**
3. Watch lights cycle and queue bars fill
4. Switch algorithm to `adaptive_cycle` → click **Switch Algorithm**
5. Observe KPI panel update in real time

### B. Headless demo (terminal)
```bash
python3 scenarios/demo.py
```
Demonstrates: fixed-cycle run, algorithm switch at tick 50, a forced safety override, and a 10-seed what-if report.

### C. What-if via API
```bash
curl -X POST http://localhost:8000/api/whatif \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{"n_runs": 20, "algorithm": "adaptive_cycle", "max_ticks": 300}'
```

### D. Run tests
```bash
make test              # all tests
make test-cov          # with coverage HTML report
```

---

## Project Structure

```
crossroads-sim/
├── sim/                   # Core domain (engine, vehicles, lights, intersection, events, KPIs)
│   ├── engine.py          # SimEngine: discrete-time loop
│   ├── vehicles.py        # Vehicle dataclass + VehicleSpec (car/truck)
│   ├── lights.py          # TrafficLight state machine, SignalPlan
│   ├── intersection.py    # Intersection, Lane
│   ├── events.py          # EventLog (append-only) + KPISnapshot
│   ├── generator.py       # Stochastic Poisson arrival generator
│   └── kpi.py             # KPICalculator
│
├── safety/
│   └── checker.py         # SafetyChecker (R1 conflicting greens, R2 skip detection)
│
├── algorithms/
│   ├── __init__.py        # Plugin registry + discover()
│   ├── null_control.py    # Amber-flash fallback
│   ├── fixed_cycle.py     # Clock-driven fixed cycle
│   ├── adaptive_cycle.py  # Traffic-aware adaptive cycle
│   └── switcher.py        # Safe mid-run algorithm switcher
│
├── persistence/
│   ├── models.py          # SQLAlchemy ORM (Layout, Scenario, Run, EventRecord, Recording)
│   ├── database.py        # Engine + session factory
│   └── crud.py            # CRUD helpers
│
├── api/
│   ├── main.py            # FastAPI app, all endpoints, WebSocket
│   ├── settings.py        # Pydantic-settings config
│   ├── schemas.py         # Pydantic request/response models
│   ├── auth.py            # Bearer token auth dependency
│   └── sim_manager.py     # Singleton sim + WS broadcaster
│
├── ui/static/
│   └── index.html         # Single-page canvas UI + KPI panel (+ optional OSM toggle)
│
├── tests/
│   ├── unit/              # Unit + API + regression tests
│   └── property/          # Hypothesis property-based tests
│
├── scenarios/
│   └── demo.py            # End-to-end headless demo
│
├── migrations/            # Alembic migrations
├── .github/workflows/ci.yml
├── .vscode/{tasks,launch}.json
├── Makefile
├── pyproject.toml         # Ruff + pytest config
└── requirements.txt
```

---

## Key Design Decisions

| Concern | Decision |
|---|---|
| **Determinism** | Single seeded `random.Random` per run; seed stored in DB + recording |
| **Event sourcing** | Append-only `EventLog`; SHA-256 checksum for regression tests |
| **Safety** | Checker between controller and lights; overrides to amber-flash with logged explanation |
| **Algorithm plugins** | `@register` decorator + `discover()` auto-loader from `algorithms/*.py` |
| **Safe switching** | `AlgorithmSwitcher` inserts 4-tick all-red intergreen before switching |
| **Multi-client WS** | `sim_manager` broadcasts `asyncio.Queue` per client; disconnect safe |
| **ORM only** | All DB access via SQLAlchemy 2.x; Alembic migrations |

---

## API Reference (key endpoints)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/algorithms` | – | List available algorithms |
| GET | `/api/layouts` | – | List intersection layouts |
| POST | `/api/layouts` | ✓ | Create layout |
| GET | `/api/scenarios` | – | List scenarios |
| POST | `/api/sim/create` | ✓ | Create simulation run |
| POST | `/api/sim/start` | ✓ | Start simulation |
| POST | `/api/sim/stop` | ✓ | Stop + persist KPIs |
| POST | `/api/sim/reset` | ✓ | Reset simulation |
| GET | `/api/sim/state` | – | Current state snapshot |
| POST | `/api/sim/switch_algorithm` | ✓ | Safe algorithm switch |
| GET | `/api/runs` | – | List past runs with KPIs |
| GET | `/api/recordings/{run_id}` | – | Full recording for playback |
| POST | `/api/whatif` | ✓ | Monte Carlo what-if report |
| WS | `/ws?token=<token>` | token | Real-time state stream |

Auth: `Authorization: Bearer dev-token` (override `API_TOKEN` env var in production).

---

## Configuration

Copy `.env.example` → `.env`:
```env
API_TOKEN=your-secret-token
SECRET_KEY=your-jwt-secret
DATABASE_URL=sqlite:///./crossroads.db
CORS_ORIGINS=["http://localhost:3000"]
WS_BROADCAST_INTERVAL_MS=200
```

---

## Reflection Template

See `REFLECTION.md` – prompts for your AI-assisted development retrospective.
