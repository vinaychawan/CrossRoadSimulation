"""
Flask application – main entrypoint.

Run with:
    python3 -m api.main
or:
    flask --app api.main run --reload
"""
from __future__ import annotations

import json
import logging
import statistics
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from flask_sock import Sock
from sqlalchemy.orm import Session

import algorithms
from algorithms.switcher import AlgorithmSwitcher
from api.settings import settings
from api.sim_manager import sim_manager
from persistence import crud
from persistence.database import get_session, init_db
from safety.checker import SafetyChecker
from sim.engine import SimConfig, SimEngine
from sim.enums import Direction
from sim.intersection import Intersection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

app = Flask(__name__, static_folder=None)
CORS(app, origins=settings.cors_origins)
sock = Sock(app)

_UI_DIR = Path(__file__).parent.parent / "ui" / "static"


@app.before_request
def _startup_once():
    if not hasattr(app, "_started"):
        app._started = True
        init_db()
        algorithms.discover()
        db = next(get_session())
        try:
            if not crud.list_layouts(db):
                layout = crud.create_layout(db, "standard_cross", "Default 4-way cross", {})
                crud.create_scenario(
                    db, "rush_hour", layout.id,
                    {"mean_interarrival": 10, "car_fraction": 0.75},
                    "fixed_cycle",
                )
        finally:
            db.close()


# ── Static / UI ──────────────────────────────────────────────────────────────

@app.route("/")
def root():
    return send_from_directory(str(_UI_DIR), "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(_UI_DIR), filename)


# ── Auth helper ───────────────────────────────────────────────────────────────

def _auth_error():
    return jsonify({"detail": "Invalid or missing bearer token"}), 401


def _get_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.args.get("token", "")


# ── Algorithms ────────────────────────────────────────────────────────────────

@app.route("/api/algorithms")
def list_algorithms():
    return jsonify(algorithms.available())


# ── Layout CRUD ───────────────────────────────────────────────────────────────

@app.route("/api/layouts", methods=["GET"])
def get_layouts():
    db = next(get_session())
    try:
        rows = crud.list_layouts(db)
        return jsonify([{"id": r.id, "name": r.name, "description": r.description, "config": r.config} for r in rows])
    finally:
        db.close()


@app.route("/api/layouts", methods=["POST"])
def post_layout():
    if _get_token() != settings.api_token:
        return _auth_error()
    body = request.get_json() or {}
    db = next(get_session())
    try:
        row = crud.create_layout(db, body["name"], body.get("description", ""), body.get("config", {}))
        return jsonify({"id": row.id, "name": row.name, "description": row.description, "config": row.config})
    finally:
        db.close()


@app.route("/api/layouts/<int:layout_id>", methods=["PUT"])
def put_layout(layout_id):
    if _get_token() != settings.api_token:
        return _auth_error()
    body = request.get_json() or {}
    db = next(get_session())
    try:
        row = crud.update_layout(db, layout_id, name=body.get("name"), description=body.get("description", ""), config=body.get("config", {}))
        if not row:
            return jsonify({"detail": "Not found"}), 404
        return jsonify({"id": row.id, "name": row.name, "description": row.description, "config": row.config})
    finally:
        db.close()


@app.route("/api/layouts/<int:layout_id>", methods=["DELETE"])
def del_layout(layout_id):
    if _get_token() != settings.api_token:
        return _auth_error()
    db = next(get_session())
    try:
        ok = crud.delete_layout(db, layout_id)
        if not ok:
            return jsonify({"detail": "Not found"}), 404
        return jsonify({"deleted": layout_id})
    finally:
        db.close()


# ── Scenario CRUD ─────────────────────────────────────────────────────────────

@app.route("/api/scenarios", methods=["GET"])
def get_scenarios():
    db = next(get_session())
    try:
        rows = crud.list_scenarios(db)
        return jsonify([
            {"id": r.id, "name": r.name, "layout_id": r.layout_id,
             "default_algorithm": r.default_algorithm, "arrival_config": r.arrival_config}
            for r in rows
        ])
    finally:
        db.close()


@app.route("/api/scenarios", methods=["POST"])
def post_scenario():
    if _get_token() != settings.api_token:
        return _auth_error()
    body = request.get_json() or {}
    db = next(get_session())
    try:
        row = crud.create_scenario(db, body["name"], body["layout_id"], body.get("arrival_config", {}), body.get("default_algorithm", "fixed_cycle"))
        return jsonify({"id": row.id, "name": row.name, "layout_id": row.layout_id, "default_algorithm": row.default_algorithm, "arrival_config": row.arrival_config})
    finally:
        db.close()


# ── Simulation control ────────────────────────────────────────────────────────

@app.route("/api/sim/create", methods=["POST"])
def create_sim():
    if _get_token() != settings.api_token:
        return _auth_error()
    body = request.get_json() or {}
    cfg = SimConfig(
        seed=body.get("seed", 42),
        algorithm=body.get("algorithm", "fixed_cycle"),
        tick_step_ms=body.get("tick_step_ms", 500),
        max_ticks=body.get("max_ticks"),
        scenario_id=body.get("scenario_id"),
    )
    run_id = sim_manager.create(cfg)
    db = next(get_session())
    try:
        crud.create_run(db, run_id=run_id, scenario_id=cfg.scenario_id, seed=cfg.seed,
                        algorithm=cfg.algorithm, tick_step_ms=cfg.tick_step_ms, max_ticks=cfg.max_ticks)
    finally:
        db.close()
    return jsonify({"run_id": run_id, "status": "created"})


@app.route("/api/sim/start", methods=["POST"])
def start_sim():
    if _get_token() != settings.api_token:
        return _auth_error()
    sim_manager.start()
    return jsonify({"status": "started"})


@app.route("/api/sim/stop", methods=["POST"])
def stop_sim():
    if _get_token() != settings.api_token:
        return _auth_error()
    sim_manager.stop()
    db = next(get_session())
    try:
        _persist_run(db)
    finally:
        db.close()
    return jsonify({"status": "stopped"})


@app.route("/api/sim/reset", methods=["POST"])
def reset_sim():
    if _get_token() != settings.api_token:
        return _auth_error()
    sim_manager.reset()
    return jsonify({"status": "reset"})


@app.route("/api/sim/state")
def sim_state():
    if sim_manager.engine is None:
        return jsonify({"status": "no_simulation"})
    return jsonify(sim_manager.engine.snapshot_state())


@app.route("/api/sim/switch_algorithm", methods=["POST"])
def switch_algorithm():
    if _get_token() != settings.api_token:
        return _auth_error()
    body = request.get_json() or {}
    algo = body.get("algorithm", "fixed_cycle")
    try:
        sim_manager.switch_algorithm(algo)
    except KeyError as e:
        return jsonify({"detail": str(e)}), 400
    return jsonify({"algorithm": algo, "status": "switching"})


# ── Runs ──────────────────────────────────────────────────────────────────────

@app.route("/api/runs")
def get_runs():
    db = next(get_session())
    try:
        rows = crud.list_runs(db)
        return jsonify([
            {"id": r.id, "run_id": r.run_id, "seed": r.seed,
             "algorithm": r.algorithm, "vehicles_passed": r.vehicles_passed,
             "avg_wait_ticks": r.avg_wait_ticks, "pct_null_control": r.pct_null_control}
            for r in rows
        ])
    finally:
        db.close()


# ── Recording ─────────────────────────────────────────────────────────────────

@app.route("/api/recordings/<run_id>")
def get_recording(run_id):
    db = next(get_session())
    try:
        rec = crud.get_recording(db, run_id)
        if not rec:
            return jsonify({"detail": "Not found"}), 404
        return jsonify({
            "run_id": run_id,
            "config": json.loads(rec.config_json),
            "snapshots": json.loads(rec.snapshots_json),
        })
    finally:
        db.close()


# ── What-if Monte Carlo ───────────────────────────────────────────────────────

@app.route("/api/whatif", methods=["POST"])
def whatif():
    if _get_token() != settings.api_token:
        return _auth_error()
    body = request.get_json() or {}
    n_runs = max(2, min(200, int(body.get("n_runs", 10))))
    algo = body.get("algorithm", "fixed_cycle")
    max_ticks = int(body.get("max_ticks", 500))
    base_seed = int(body.get("base_seed", 0))

    wait_list, thr_list, null_list = [], [], []
    for i in range(n_runs):
        cfg = SimConfig(seed=base_seed + i, algorithm=algo, max_ticks=max_ticks)
        ix = Intersection()
        eng = SimEngine(cfg, ix, AlgorithmSwitcher(algo), SafetyChecker())
        eng.start()
        while eng.running:
            eng.step()
        kpi = eng._kpi.snapshot(eng.tick, ix, eng._active_vehicles)
        wait_list.append(kpi.avg_wait_ticks)
        thr_list.append(kpi.throughput_per_100_ticks)
        null_list.append(kpi.pct_null_control)

    def _p95(lst):
        s = sorted(lst)
        return s[min(int(len(s) * 0.95), len(s) - 1)]

    return jsonify({
        "n_runs": n_runs, "algorithm": algo,
        "avg_wait_min": min(wait_list), "avg_wait_mean": statistics.mean(wait_list), "avg_wait_p95": _p95(wait_list),
        "throughput_min": min(thr_list), "throughput_mean": statistics.mean(thr_list), "throughput_p95": _p95(thr_list),
        "pct_null_min": min(null_list), "pct_null_mean": statistics.mean(null_list), "pct_null_p95": _p95(null_list),
    })


# ── WebSocket ─────────────────────────────────────────────────────────────────

@sock.route("/ws")
def websocket(ws):  # pragma: no cover
    token = request.args.get("token", "")
    if token != settings.api_token:
        ws.close(message=b"Unauthorized")
        return

    interval = settings.ws_broadcast_interval_ms / 1000.0

    def _ticker():
        while not _stop.is_set():
            time.sleep(interval)
            sim_manager.step()
            if sim_manager.engine:
                snap = sim_manager.engine.snapshot_state()
                try:
                    ws.send(json.dumps(snap))
                except Exception:
                    _stop.set()

    _stop = threading.Event()
    t = threading.Thread(target=_ticker, daemon=True)
    t.start()

    try:
        while True:
            try:
                msg = ws.receive(timeout=1)
                if msg is None:
                    break
                cmd = json.loads(msg)
                _handle_ws_command(cmd)
            except Exception:
                break
    finally:
        _stop.set()


def _handle_ws_command(cmd: dict) -> None:  # pragma: no cover
    action = cmd.get("action")
    if action == "start":
        sim_manager.start()
    elif action == "stop":
        sim_manager.stop()
    elif action == "reset":
        sim_manager.reset()
    elif action == "switch_algorithm":
        try:
            sim_manager.switch_algorithm(cmd.get("algorithm", "fixed_cycle"))
        except KeyError:
            pass


# ── Persistence helper ────────────────────────────────────────────────────────

def _persist_run(db) -> None:
    engine = sim_manager.engine
    cfg = sim_manager.config
    if not engine or not cfg:
        return
    kpi = engine._kpi.snapshot(engine.tick, engine.intersection, engine._active_vehicles)
    run = crud.get_run(db, cfg.run_id)
    if run:
        run.avg_wait_ticks = kpi.avg_wait_ticks
        run.max_wait_ticks = kpi.max_wait_ticks
        run.throughput_per_100_ticks = kpi.throughput_per_100_ticks
        run.total_stops = kpi.total_stops
        run.pct_null_control = kpi.pct_null_control
        run.vehicles_passed = kpi.vehicles_passed
        run.event_log_checksum = engine.event_log.checksum()
        db.commit()
    cfg_dict = {"run_id": cfg.run_id, "seed": cfg.seed, "algorithm": cfg.algorithm, "tick_step_ms": cfg.tick_step_ms}
    crud.save_recording(db, cfg.run_id, cfg_dict, sim_manager.snapshots)
    crud.save_events(db, cfg.run_id, [e.to_dict() for e in engine.event_log.all_events()])


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000, threaded=True)

