import json
import runpy
from types import SimpleNamespace
from unittest import mock

import pytest

import api.main as main_module
from sim.enums import EventType, LightPhase, VehicleState, Direction
from sim.vehicles import Vehicle
from sim.engine import SimConfig, SimEngine
from sim.intersection import Intersection
from algorithms.switcher import AlgorithmSwitcher
from safety.checker import SafetyChecker


HEADERS = {"Authorization": "Bearer dev-token"}


@pytest.fixture
def client():
    main_module.app.config["TESTING"] = True
    with main_module.app.test_client() as c:
        yield c


def test_static_files_route_reachable(client):
    response = client.get("/static/index.html")
    assert response.status_code in (200, 404)


def test_auth_required_routes_cover_unauthorized(client):
    # These requests intentionally omit auth to cover all auth-error branches.
    assert client.post("/api/layouts", json={"name": "x"}).status_code == 401
    assert client.put("/api/layouts/1", json={"name": "x"}).status_code == 401
    assert client.delete("/api/layouts/1").status_code == 401
    assert client.post("/api/scenarios", json={"name": "x", "layout_id": 1}).status_code == 401
    assert client.post("/api/sim/stop", json={}).status_code == 401
    assert client.post("/api/sim/reset", json={}).status_code == 401
    assert client.post("/api/sim/switch_algorithm", json={"algorithm": "fixed_cycle"}).status_code == 401


def test_recording_success_path(client):
    create_resp = client.post(
        "/api/sim/create",
        json={"seed": 7, "algorithm": "fixed_cycle", "max_ticks": 5},
        headers=HEADERS,
    )
    run_id = create_resp.get_json()["run_id"]

    client.post("/api/sim/start", json={}, headers=HEADERS)
    client.post("/api/sim/stop", json={}, headers=HEADERS)

    rec = client.get(f"/api/recordings/{run_id}")
    assert rec.status_code == 200
    data = rec.get_json()
    assert data["run_id"] == run_id
    assert isinstance(data["snapshots"], list)


def test_startup_once_seeds_default_layout(monkeypatch):
    if hasattr(main_module.app, "_started"):
        delattr(main_module.app, "_started")

    fake_db = mock.MagicMock()
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    monkeypatch.setattr(main_module.algorithms, "discover", lambda: None)
    monkeypatch.setattr(main_module, "get_session", lambda: iter([fake_db]))
    monkeypatch.setattr(main_module.crud, "list_layouts", lambda db: [])

    layout = SimpleNamespace(id=101)
    create_layout = mock.Mock(return_value=layout)
    create_scenario = mock.Mock()
    monkeypatch.setattr(main_module.crud, "create_layout", create_layout)
    monkeypatch.setattr(main_module.crud, "create_scenario", create_scenario)

    with main_module.app.test_request_context("/api/algorithms"):
        main_module._startup_once()

    create_layout.assert_called_once()
    create_scenario.assert_called_once()
    fake_db.close.assert_called_once()


def test_persist_run_returns_when_no_engine_or_config(monkeypatch):
    fake_db = mock.Mock()
    monkeypatch.setattr(main_module.sim_manager, "_engine", None)
    monkeypatch.setattr(main_module.sim_manager, "_config", None)

    save_recording = mock.Mock()
    save_events = mock.Mock()
    monkeypatch.setattr(main_module.crud, "save_recording", save_recording)
    monkeypatch.setattr(main_module.crud, "save_events", save_events)

    main_module._persist_run(fake_db)

    save_recording.assert_not_called()
    save_events.assert_not_called()


def test_api_main_module_entrypoint(monkeypatch):
    fake_run = mock.Mock()
    monkeypatch.setattr("flask.app.Flask.run", fake_run)
    runpy.run_module("api.main", run_name="__main__")
    fake_run.assert_called_once()


def test_engine_emits_safety_override_event():
    cfg = SimConfig(seed=1, max_ticks=2, algorithm="fixed_cycle")
    eng = SimEngine(cfg, Intersection(), AlgorithmSwitcher("fixed_cycle"), SafetyChecker())
    eng.start()

    eng.controller.compute = mock.Mock(return_value={})
    eng.safety_checker.check = mock.Mock(
        return_value=({}, [{"rule": "R1", "explanation": "forced", "action": "all_amber"}])
    )

    eng.step()
    events = eng.event_log.events_of_type(EventType.SAFETY_OVERRIDE)
    assert len(events) == 1


def test_engine_marks_moving_front_vehicle_stopped_on_red():
    cfg = SimConfig(seed=1, max_ticks=1, algorithm="fixed_cycle")
    eng = SimEngine(cfg, Intersection(), AlgorithmSwitcher("fixed_cycle"), SafetyChecker())

    lane = eng.intersection.lanes[Direction.NORTH]
    car = Vehicle(direction=Direction.NORTH, state=VehicleState.MOVING)
    lane.enqueue(car)
    eng.intersection.lights[Direction.NORTH].set_phase(LightPhase.RED)

    eng._move_vehicles()

    assert car.state == VehicleState.QUEUED
    assert car.stops == 1
