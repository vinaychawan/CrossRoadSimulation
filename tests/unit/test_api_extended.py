"""
Extended API tests — full coverage of api/main.py and api/sim_manager.py.
Uses Flask test client (sync, no asyncio).
"""
import json
import uuid
import pytest
from api.main import app
from api.sim_manager import SimManager
from api.settings import settings
from sim.engine import SimConfig


def _uid() -> str:
    """Generate a short unique suffix to avoid DB UNIQUE constraint collisions."""
    return uuid.uuid4().hex[:8]

HEADERS = {"Authorization": "Bearer dev-token"}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def fresh_manager():
    return SimManager()


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_auth_via_query_param(client):
    r = client.post(f"/api/sim/create?token={settings.api_token}",
                    json={"seed": 1, "algorithm": "fixed_cycle"})
    assert r.status_code == 200


def test_auth_missing_returns_401(client):
    r = client.post("/api/sim/start", json={})
    assert r.status_code == 401


def test_auth_wrong_token_returns_401(client):
    r = client.post("/api/sim/start",
                    headers={"Authorization": "Bearer wrong-token"})
    assert r.status_code == 401


# ── Root / static ─────────────────────────────────────────────────────────────

def test_root_serves_index(client):
    r = client.get("/")
    # May 404 if index.html doesn't exist but route should be reachable
    assert r.status_code in (200, 404)


# ── Algorithms ────────────────────────────────────────────────────────────────

def test_list_algorithms_returns_list(client):
    r = client.get("/api/algorithms")
    assert r.status_code == 200
    data = json.loads(r.data)
    assert isinstance(data, list)
    assert "fixed_cycle" in data


# ── Layout CRUD ───────────────────────────────────────────────────────────────

def test_get_layouts(client):
    r = client.get("/api/layouts")
    assert r.status_code == 200
    assert isinstance(json.loads(r.data), list)


def test_post_layout(client):
    name = f"api_test_layout_{_uid()}"
    r = client.post("/api/layouts",
                    json={"name": name, "description": "test"},
                    headers=HEADERS)
    assert r.status_code == 200
    d = json.loads(r.data)
    assert d["name"] == name


def test_put_layout(client):
    uid = _uid()
    r = client.post("/api/layouts",
                    json={"name": f"api_put_layout_{uid}", "description": "old"},
                    headers=HEADERS)
    lid = json.loads(r.data)["id"]
    new_name = f"api_put_updated_{uid}"
    r2 = client.put(f"/api/layouts/{lid}",
                    json={"name": new_name, "description": "new"},
                    headers=HEADERS)
    assert r2.status_code == 200
    assert json.loads(r2.data)["name"] == new_name


def test_put_layout_not_found(client):
    r = client.put("/api/layouts/99999",
                   json={"name": "x", "description": "y"},
                   headers=HEADERS)
    assert r.status_code == 404


def test_delete_layout(client):
    r = client.post("/api/layouts",
                    json={"name": f"api_del_layout_{_uid()}"},
                    headers=HEADERS)
    lid = json.loads(r.data)["id"]
    r2 = client.delete(f"/api/layouts/{lid}", headers=HEADERS)
    assert r2.status_code == 200
    assert json.loads(r2.data)["deleted"] == lid


def test_delete_layout_not_found(client):
    r = client.delete("/api/layouts/99999", headers=HEADERS)
    assert r.status_code == 404


# ── Scenario CRUD ─────────────────────────────────────────────────────────────

def test_get_scenarios(client):
    r = client.get("/api/scenarios")
    assert r.status_code == 200


def test_post_scenario(client):
    layouts = json.loads(client.get("/api/layouts").data)
    if not layouts:
        client.post("/api/layouts", json={"name": f"scn_base_{_uid()}"}, headers=HEADERS)
        layouts = json.loads(client.get("/api/layouts").data)
    lid = layouts[0]["id"]
    scn_name = f"api_test_scenario_{_uid()}"
    r = client.post("/api/scenarios",
                    json={"name": scn_name, "layout_id": lid,
                          "arrival_config": {}, "default_algorithm": "fixed_cycle"},
                    headers=HEADERS)
    assert r.status_code == 200
    assert json.loads(r.data)["name"] == scn_name


# ── Sim lifecycle ─────────────────────────────────────────────────────────────

def test_sim_full_lifecycle(client):
    # Create
    r = client.post("/api/sim/create",
                    json={"seed": 10, "algorithm": "fixed_cycle", "max_ticks": 20},
                    headers=HEADERS)
    assert r.status_code == 200
    run_id = json.loads(r.data)["run_id"]

    # State before start
    r2 = client.get("/api/sim/state")
    assert r2.status_code == 200

    # Start
    r3 = client.post("/api/sim/start", json={}, headers=HEADERS)
    assert r3.status_code == 200

    # Stop
    r4 = client.post("/api/sim/stop", json={}, headers=HEADERS)
    assert r4.status_code == 200

    # Reset
    r5 = client.post("/api/sim/reset", json={}, headers=HEADERS)
    assert r5.status_code == 200


def test_sim_state_no_simulation(client):
    # Reset sim_manager
    from api import sim_manager as sm_module
    sm_module.sim_manager._engine = None
    r = client.get("/api/sim/state")
    assert r.status_code == 200
    assert json.loads(r.data)["status"] == "no_simulation"


def test_switch_algorithm(client):
    client.post("/api/sim/create",
                json={"seed": 1, "algorithm": "fixed_cycle"},
                headers=HEADERS)
    r = client.post("/api/sim/switch_algorithm",
                    json={"algorithm": "adaptive_cycle"},
                    headers=HEADERS)
    assert r.status_code == 200
    assert json.loads(r.data)["algorithm"] == "adaptive_cycle"


def test_switch_algorithm_invalid(client):
    client.post("/api/sim/create",
                json={"seed": 1, "algorithm": "fixed_cycle"},
                headers=HEADERS)
    r = client.post("/api/sim/switch_algorithm",
                    json={"algorithm": "does_not_exist_xyz"},
                    headers=HEADERS)
    assert r.status_code == 400


# ── Runs ──────────────────────────────────────────────────────────────────────

def test_get_runs(client):
    r = client.get("/api/runs")
    assert r.status_code == 200
    assert isinstance(json.loads(r.data), list)


# ── Recordings ────────────────────────────────────────────────────────────────

def test_get_recording_not_found(client):
    r = client.get("/api/recordings/nonexistent_run_id")
    assert r.status_code == 404


# ── What-if ───────────────────────────────────────────────────────────────────

def test_whatif_endpoint(client):
    r = client.post("/api/whatif",
                    json={"n_runs": 2, "algorithm": "null_control",
                          "max_ticks": 20, "base_seed": 0},
                    headers=HEADERS)
    assert r.status_code == 200
    d = json.loads(r.data)
    assert d["n_runs"] == 2
    assert "avg_wait_mean" in d
    assert "throughput_mean" in d
    assert "pct_null_mean" in d


def test_whatif_clamps_n_runs(client):
    r = client.post("/api/whatif",
                    json={"n_runs": 1, "algorithm": "null_control", "max_ticks": 5},
                    headers=HEADERS)
    assert r.status_code == 200
    d = json.loads(r.data)
    assert d["n_runs"] == 2  # clamped to min 2


def test_whatif_unauthorized(client):
    r = client.post("/api/whatif", json={"n_runs": 2})
    assert r.status_code == 401


# ── SimManager ────────────────────────────────────────────────────────────────

def test_sim_manager_step_no_engine(fresh_manager):
    fresh_manager.step()  # should not raise when engine is None


def test_sim_manager_start_no_engine(fresh_manager):
    fresh_manager.start()  # should not raise


def test_sim_manager_stop_no_engine(fresh_manager):
    fresh_manager.stop()  # should not raise


def test_sim_manager_reset_no_engine(fresh_manager):
    fresh_manager.reset()  # should not raise


def test_sim_manager_switch_no_engine(fresh_manager):
    fresh_manager.switch_algorithm("fixed_cycle")  # should not raise


def test_sim_manager_create_and_step(fresh_manager):
    cfg = SimConfig(seed=1, max_ticks=10, algorithm="fixed_cycle")
    run_id = fresh_manager.create(cfg)
    assert isinstance(run_id, str)
    fresh_manager.start()
    for _ in range(5):
        fresh_manager.step()
    assert fresh_manager.engine is not None
    assert fresh_manager.config is not None
    assert isinstance(fresh_manager.snapshots, list)


def test_sim_manager_step_not_running(fresh_manager):
    """step() when engine exists but isn't running should not advance tick."""
    cfg = SimConfig(seed=1, algorithm="fixed_cycle")
    fresh_manager.create(cfg)
    # Don't start
    fresh_manager.step()
    assert fresh_manager.engine.tick == 0


def test_sim_manager_snapshots_accumulate(fresh_manager):
    cfg = SimConfig(seed=3, max_ticks=50, algorithm="fixed_cycle",
                    kpi_sample_interval=5)
    fresh_manager.create(cfg)
    fresh_manager.start()
    for _ in range(10):
        fresh_manager.step()
    assert len(fresh_manager.snapshots) == 10


# ── Settings ──────────────────────────────────────────────────────────────────

def test_settings_defaults():
    assert isinstance(settings.api_token, str)
    assert isinstance(settings.cors_origins, list)
    assert isinstance(settings.ws_broadcast_interval_ms, int)
    assert settings.ws_broadcast_interval_ms > 0
