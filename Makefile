.PHONY: install run test test-cov test-unit-cov-100 lint fmt migrate seed-db

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

run:
	.venv/bin/python3 -m api.main

test:
	.venv/bin/python3 -m pytest

test-cov:
	.venv/bin/python3 -m pytest --cov --cov-report=term-missing --cov-report=html

test-unit-cov-100:
	bash scripts/unit_coverage_gate.sh

lint:
	.venv/bin/ruff check .

fmt:
	.venv/bin/ruff format .

migrate:
	.venv/bin/alembic upgrade head

seed-db:
	.venv/bin/python3 -c "from api.main import startup; startup()"

# Quick headless demo run (no UI needed)
demo:
	.venv/bin/python3 -c "
from algorithms import discover; discover()
from algorithms.switcher import AlgorithmSwitcher
from safety.checker import SafetyChecker
from sim.engine import SimConfig, SimEngine
from sim.intersection import Intersection
cfg = SimConfig(seed=42, max_ticks=200, algorithm='fixed_cycle')
eng = SimEngine(cfg, Intersection(), AlgorithmSwitcher('fixed_cycle'), SafetyChecker())
eng.start()
while eng.running: eng.step()
kpi = eng._kpi.snapshot(eng.tick, eng.intersection, eng._active_vehicles)
print(f'Passed: {kpi.vehicles_passed}  AvgWait: {kpi.avg_wait_ticks:.1f}  NullCtrl: {kpi.pct_null_control:.1f}%')
"
