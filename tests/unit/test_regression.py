"""Regression test: same seed + config must reproduce identical event checksum."""
import pytest
from sim.engine import SimConfig, SimEngine
from sim.intersection import Intersection
from algorithms.switcher import AlgorithmSwitcher
from algorithms import discover
from safety.checker import SafetyChecker


discover()


_KNOWN = [
    (42,  "fixed_cycle",    50),
    (0,   "adaptive_cycle", 80),
    (123, "fixed_cycle",    30),
]


@pytest.mark.parametrize("seed,algo,ticks", _KNOWN)
def test_regression_checksum_stable(seed, algo, ticks):
    """Two runs with identical (seed, algo, ticks) produce the same checksum."""
    def _run():
        cfg = SimConfig(seed=seed, max_ticks=ticks, algorithm=algo)
        ix = Intersection()
        eng = SimEngine(cfg, ix, AlgorithmSwitcher(algo), SafetyChecker())
        eng.start()
        while eng.running:
            eng.step()
        return eng.event_log.checksum()

    assert _run() == _run(), f"Non-deterministic for seed={seed} algo={algo} ticks={ticks}"
