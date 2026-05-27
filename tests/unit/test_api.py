"""Flask endpoint smoke tests."""
import json

import pytest

from api.main import app

HEADERS = {"Authorization": "Bearer dev-token"}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_list_algorithms(client):
    r = client.get("/api/algorithms")
    assert r.status_code == 200
    data = json.loads(r.data)
    assert "fixed_cycle" in data


def test_create_and_start_sim(client):
    r = client.post(
        "/api/sim/create",
        json={"seed": 1, "algorithm": "fixed_cycle", "max_ticks": 10},
        headers=HEADERS,
    )
    assert r.status_code == 200
    data = json.loads(r.data)
    assert "run_id" in data

    r2 = client.post("/api/sim/start", json={}, headers=HEADERS)
    assert r2.status_code == 200


def test_sim_state(client):
    client.post("/api/sim/create", json={"seed": 0, "algorithm": "fixed_cycle"}, headers=HEADERS)
    r = client.get("/api/sim/state")
    assert r.status_code == 200


def test_layouts_crud(client):
    # Create
    r = client.post(
        "/api/layouts",
        json={"name": "test_layout_x", "description": "test"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    layout_id = json.loads(r.data)["id"]

    # List
    r2 = client.get("/api/layouts")
    ids = [l["id"] for l in json.loads(r2.data)]
    assert layout_id in ids

    # Delete
    r3 = client.delete(f"/api/layouts/{layout_id}", headers=HEADERS)
    assert r3.status_code == 200


def test_whatif_runner(client):
    r = client.post(
        "/api/whatif",
        json={"n_runs": 3, "algorithm": "fixed_cycle", "max_ticks": 30, "base_seed": 10},
        headers=HEADERS,
    )
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["n_runs"] == 3
    assert "avg_wait_mean" in data


def test_unauthorized_returns_401(client):
    r = client.post("/api/sim/create", json={})
    assert r.status_code == 401

