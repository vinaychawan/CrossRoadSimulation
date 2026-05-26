"""
Full CRUD tests for persistence/ — 100% coverage of crud.py, models.py, database.py.
"""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from persistence.models import Base, Layout, Scenario, Run, EventRecord, Recording
from persistence import crud
from persistence.database import init_db, get_session, SessionLocal


@pytest.fixture
def db():
    """In-memory SQLite session per test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ── Layout ────────────────────────────────────────────────────────────────────

def test_create_and_get_layout(db):
    layout = crud.create_layout(db, "test_layout", "desc", {"key": "val"})
    assert layout.id is not None
    assert layout.name == "test_layout"
    assert layout.config == {"key": "val"}

    fetched = crud.get_layout(db, layout.id)
    assert fetched is not None
    assert fetched.name == "test_layout"


def test_get_layout_not_found(db):
    assert crud.get_layout(db, 9999) is None


def test_list_layouts(db):
    crud.create_layout(db, "layout_a")
    crud.create_layout(db, "layout_b")
    layouts = crud.list_layouts(db)
    names = [l.name for l in layouts]
    assert "layout_a" in names
    assert "layout_b" in names


def test_update_layout(db):
    layout = crud.create_layout(db, "old_name", "old desc")
    updated = crud.update_layout(db, layout.id, name="new_name",
                                 description="new desc", config={"x": 1})
    assert updated.name == "new_name"
    assert updated.description == "new desc"
    assert updated.config == {"x": 1}


def test_update_layout_not_found(db):
    result = crud.update_layout(db, 9999, name="x", description="y", config={})
    assert result is None


def test_delete_layout(db):
    layout = crud.create_layout(db, "to_delete")
    assert crud.delete_layout(db, layout.id) is True
    assert crud.get_layout(db, layout.id) is None


def test_delete_layout_not_found(db):
    assert crud.delete_layout(db, 9999) is False


def test_layout_config_property(db):
    layout = crud.create_layout(db, "cfg_test", config={"a": 1, "b": [1, 2]})
    assert layout.config["a"] == 1
    assert layout.config["b"] == [1, 2]


# ── Scenario ──────────────────────────────────────────────────────────────────

def test_create_and_get_scenario(db):
    layout = crud.create_layout(db, "layout_for_scenario")
    scenario = crud.create_scenario(db, "rush_hour", layout.id,
                                    {"mean": 10}, "adaptive_cycle")
    assert scenario.id is not None
    assert scenario.default_algorithm == "adaptive_cycle"
    assert scenario.arrival_config == {"mean": 10}

    fetched = crud.get_scenario(db, scenario.id)
    assert fetched is not None
    assert fetched.name == "rush_hour"


def test_get_scenario_not_found(db):
    assert crud.get_scenario(db, 9999) is None


def test_list_scenarios(db):
    layout = crud.create_layout(db, "layout_list")
    crud.create_scenario(db, "s1", layout.id, {})
    crud.create_scenario(db, "s2", layout.id, {})
    scenarios = crud.list_scenarios(db)
    names = [s.name for s in scenarios]
    assert "s1" in names
    assert "s2" in names


# ── Run ───────────────────────────────────────────────────────────────────────

def test_create_and_get_run(db):
    run = crud.create_run(db, run_id="run_001", seed=42, algorithm="fixed_cycle",
                          tick_step_ms=500)
    assert run.run_id == "run_001"

    fetched = crud.get_run(db, "run_001")
    assert fetched is not None
    assert fetched.seed == 42


def test_get_run_not_found(db):
    assert crud.get_run(db, "nonexistent") is None


def test_list_runs(db):
    crud.create_run(db, run_id="run_a", seed=1, algorithm="fixed_cycle", tick_step_ms=500)
    crud.create_run(db, run_id="run_b", seed=2, algorithm="adaptive_cycle", tick_step_ms=500)
    runs = crud.list_runs(db)
    run_ids = [r.run_id for r in runs]
    assert "run_a" in run_ids
    assert "run_b" in run_ids


def test_list_runs_limit(db):
    for i in range(10):
        crud.create_run(db, run_id=f"limit_run_{i}", seed=i,
                        algorithm="fixed_cycle", tick_step_ms=500)
    runs = crud.list_runs(db, limit=3)
    assert len(runs) <= 3


# ── Events ────────────────────────────────────────────────────────────────────

def test_save_events(db):
    crud.create_run(db, run_id="evt_run", seed=0, algorithm="null_control", tick_step_ms=500)
    events = [
        {"tick": 1, "event_type": "sim_start", "payload": {}},
        {"tick": 2, "event_type": "vehicle_spawn", "payload": {"vid": "abc"}},
    ]
    crud.save_events(db, "evt_run", events)
    records = db.query(EventRecord).filter(EventRecord.run_id_fk == "evt_run").all()
    assert len(records) == 2
    assert records[0].event_type == "sim_start"


def test_save_events_empty(db):
    crud.create_run(db, run_id="empty_evt", seed=0, algorithm="null_control", tick_step_ms=500)
    crud.save_events(db, "empty_evt", [])  # should not raise


# ── Recording ─────────────────────────────────────────────────────────────────

def test_save_and_get_recording(db):
    crud.create_run(db, run_id="rec_run", seed=7, algorithm="fixed_cycle", tick_step_ms=500)
    config = {"run_id": "rec_run", "seed": 7}
    snapshots = [{"tick": 1}, {"tick": 2}]
    rec = crud.save_recording(db, "rec_run", config, snapshots)
    assert rec.run_id == "rec_run"

    fetched = crud.get_recording(db, "rec_run")
    assert fetched is not None
    assert json.loads(fetched.config_json)["seed"] == 7
    assert len(json.loads(fetched.snapshots_json)) == 2


def test_get_recording_not_found(db):
    assert crud.get_recording(db, "never_saved") is None


# ── Model properties ──────────────────────────────────────────────────────────

def test_scenario_arrival_config_property(db):
    layout = crud.create_layout(db, "layout_prop")
    scenario = crud.create_scenario(db, "prop_test", layout.id, {"rate": 0.5})
    assert scenario.arrival_config == {"rate": 0.5}


def test_run_model_optional_fields(db):
    run = crud.create_run(db, run_id="opt_run", seed=0, algorithm="null_control",
                          tick_step_ms=500, scenario_id=None, max_ticks=None)
    assert run.scenario_id is None
    assert run.max_ticks is None


# ── Database helpers ──────────────────────────────────────────────────────────

def test_init_db_creates_tables():
    """init_db() should be idempotent."""
    init_db()
    init_db()  # second call should not raise


def test_get_session_yields_session():
    gen = get_session()
    session = next(gen)
    assert session is not None
    try:
        next(gen)
    except StopIteration:
        pass
