"""CRUD helpers for layouts, scenarios, and runs."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from persistence.models import EventRecord, Layout, Recording, Run, Scenario

# ── Layout ──────────────────────────────────────────────────────────────────

def create_layout(db: Session, name: str, description: str = "", config: dict | None = None) -> Layout:
    obj = Layout(name=name, description=description, config_json=json.dumps(config or {}))
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_layout(db: Session, layout_id: int) -> Layout | None:
    return db.get(Layout, layout_id)


def list_layouts(db: Session) -> list[Layout]:
    return db.query(Layout).all()


def update_layout(db: Session, layout_id: int, **kwargs) -> Layout | None:
    obj = db.get(Layout, layout_id)
    if not obj:
        return None
    for k, v in kwargs.items():
        if k == "config":
            obj.config_json = json.dumps(v)
        else:
            setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_layout(db: Session, layout_id: int) -> bool:
    obj = db.get(Layout, layout_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


# ── Scenario ────────────────────────────────────────────────────────────────

def create_scenario(db: Session, name: str, layout_id: int, arrival_config: dict, algorithm: str = "fixed_cycle") -> Scenario:
    obj = Scenario(
        name=name,
        layout_id=layout_id,
        arrival_config_json=json.dumps(arrival_config),
        default_algorithm=algorithm,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_scenario(db: Session, scenario_id: int) -> Scenario | None:
    return db.get(Scenario, scenario_id)


def list_scenarios(db: Session) -> list[Scenario]:
    return db.query(Scenario).all()


# ── Run ─────────────────────────────────────────────────────────────────────

def create_run(db: Session, **kwargs) -> Run:
    obj = Run(**kwargs)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_run(db: Session, run_id: str) -> Run | None:
    return db.query(Run).filter(Run.run_id == run_id).first()


def list_runs(db: Session, limit: int = 50) -> list[Run]:
    return db.query(Run).order_by(Run.started_at.desc()).limit(limit).all()


def save_events(db: Session, run_id: str, events: list[dict]) -> None:
    for e in events:
        db.add(EventRecord(
            run_id_fk=run_id,
            tick=e["tick"],
            event_type=e["event_type"],
            payload_json=json.dumps(e.get("payload", {})),
        ))
    db.commit()


def save_recording(db: Session, run_id: str, config: dict, snapshots: list[dict]) -> Recording:
    rec = Recording(
        run_id=run_id,
        config_json=json.dumps(config),
        snapshots_json=json.dumps(snapshots),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def get_recording(db: Session, run_id: str) -> Recording | None:
    return db.query(Recording).filter(Recording.run_id == run_id).first()
