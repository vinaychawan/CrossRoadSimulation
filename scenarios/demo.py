"""
Sample scenario: demonstrates algorithm switching, safety override, and what-if runner.

Run with:
    python3 scenarios/demo.py
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from algorithms import discover
from algorithms.switcher import AlgorithmSwitcher
from safety.checker import SafetyChecker
from sim.engine import SimConfig, SimEngine
from sim.enums import Direction, LightPhase
from sim.intersection import Intersection

discover()

# ── 1. Basic fixed-cycle run ──────────────────────────────────────────────

print("=== Demo 1: Fixed-cycle 200 ticks ===")
cfg = SimConfig(seed=42, max_ticks=200, algorithm="fixed_cycle")
ix = Intersection()
switcher = AlgorithmSwitcher("fixed_cycle")
eng = SimEngine(cfg, ix, switcher, SafetyChecker())
eng.start()
while eng.running:
    eng.step()

kpi = eng._kpi.snapshot(eng.tick, ix, eng._active_vehicles)
print(f"  Passed: {kpi.vehicles_passed}  AvgWait: {kpi.avg_wait_ticks:.1f}  NullCtrl: {kpi.pct_null_control:.1f}%")
print(f"  Event log checksum: {eng.event_log.checksum()[:16]}…")

# ── 2. Mid-run algorithm switch ───────────────────────────────────────────

print("\n=== Demo 2: Algorithm switch fixed → adaptive at tick 50 ===")
cfg2 = SimConfig(seed=42, max_ticks=200, algorithm="fixed_cycle")
ix2 = Intersection()
switcher2 = AlgorithmSwitcher("fixed_cycle")
eng2 = SimEngine(cfg2, ix2, switcher2, SafetyChecker())
eng2.start()
switched = False
while eng2.running:
    eng2.step()
    if eng2.tick == 50 and not switched:
        switcher2.request_switch("adaptive_cycle")
        print(f"  [tick {eng2.tick}] Requested switch → adaptive_cycle")
        switched = True
kpi2 = eng2._kpi.snapshot(eng2.tick, ix2, eng2._active_vehicles)
print(f"  Passed: {kpi2.vehicles_passed}  AvgWait: {kpi2.avg_wait_ticks:.1f}")

# ── 3. Force a safety override ────────────────────────────────────────────

print("\n=== Demo 3: Safety override (conflicting greens) ===")
checker = SafetyChecker()
ix3 = Intersection()
# Deliberately conflicting commands
bad_commands = {
    Direction.NORTH: LightPhase.GREEN,
    Direction.EAST: LightPhase.GREEN,
    Direction.SOUTH: LightPhase.RED,
    Direction.WEST: LightPhase.RED,
}
safe, violations = checker.check(bad_commands, ix3)
for v in violations:
    print(f"  VIOLATION: {v['rule']}")
    print(f"  Explanation: {v['explanation']}")
    print(f"  Override: {v['override']}")
print(f"  Output phases: { {d.value: p.value for d, p in safe.items()} }")

# ── 4. What-if Monte Carlo ─────────────────────────────────────────────────

print("\n=== Demo 4: What-if runner (10 seeds, fixed_cycle, 100 ticks) ===")
import statistics as _stats
results = []
for i in range(10):
    cfg_i = SimConfig(seed=i, max_ticks=100, algorithm="fixed_cycle")
    ix_i = Intersection()
    eng_i = SimEngine(cfg_i, ix_i, AlgorithmSwitcher("fixed_cycle"), SafetyChecker())
    eng_i.start()
    while eng_i.running:
        eng_i.step()
    kpi_i = eng_i._kpi.snapshot(eng_i.tick, ix_i, eng_i._active_vehicles)
    results.append(kpi_i.avg_wait_ticks)

wait_sorted = sorted(results)
p95_idx = int(len(wait_sorted) * 0.95)
print(f"  AvgWait: min={min(results):.1f}  mean={_stats.mean(results):.1f}  p95={wait_sorted[min(p95_idx, len(wait_sorted)-1)]:.1f}")
print("\nDemo complete ✓")
