"""Shared pytest fixtures."""
import os
os.environ.setdefault("MPLBACKEND", "Agg")

import pytest
from sim.engine import SimConfig, SimEngine
from sim.intersection import Intersection
from algorithms.switcher import AlgorithmSwitcher
from algorithms import discover
from safety.checker import SafetyChecker


@pytest.fixture(autouse=True, scope="session")
def load_algorithms():
    discover()


@pytest.fixture
def default_config():
    return SimConfig(seed=0, max_ticks=100, algorithm="fixed_cycle")


@pytest.fixture
def engine(default_config):
    ix = Intersection()
    switcher = AlgorithmSwitcher(default_config.algorithm)
    checker = SafetyChecker()
    eng = SimEngine(default_config, ix, switcher, checker)
    eng.start()
    return eng
