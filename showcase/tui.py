"""
Textual TUI live dashboard for the crossroads simulation.

Run with:
    python3 -m showcase.tui
"""
from __future__ import annotations

import threading
import time
from collections import deque

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    Log,
    ProgressBar,
    RichLog,
    Static,
)
from textual.timer import Timer

import algorithms
from algorithms.switcher import AlgorithmSwitcher
from safety.checker import SafetyChecker
from sim.engine import SimConfig, SimEngine
from sim.enums import Direction, LightPhase
from sim.intersection import Intersection

algorithms.discover()

# ── Phase colours (ANSI) ─────────────────────────────────────────────────────
_PHASE_STYLE = {
    LightPhase.GREEN: "bold green",
    LightPhase.YELLOW: "bold yellow",
    LightPhase.RED: "bold red",
    LightPhase.AMBER_FLASH: "bold dark_orange",
}

_PHASE_ICON = {
    LightPhase.GREEN: "●",
    LightPhase.YELLOW: "◑",
    LightPhase.RED: "○",
    LightPhase.AMBER_FLASH: "◈",
}


def _phase_str(phase: LightPhase) -> str:
    icon = _PHASE_ICON[phase]
    return f"[{_PHASE_STYLE[phase]}]{icon} {phase.value.upper()}[/]"


# ── Intersection ASCII art renderer ──────────────────────────────────────────

def render_intersection(lights: dict[Direction, LightPhase], queues: dict[Direction, int]) -> str:
    """Return a coloured ASCII intersection map."""
    def _light(d: Direction) -> str:
        ph = lights[d]
        c = {"green": "32", "yellow": "33", "red": "31", "amber_flash": "33;5"}[ph.value]
        icon = _PHASE_ICON[ph]
        return f"\033[{c}m{icon}\033[0m"

    def _q(d: Direction) -> str:
        q = queues[d]
        bar = "█" * min(q, 8)
        return f"{bar:<8} {q:2d}"

    N, S, E, W = Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST
    nl = _light(N); sl = _light(S); el = _light(E); wl = _light(W)

    lines = [
        f"              {_q(N)}",
        f"              ↓  N",
        f"         ┌────{nl}────┐",
        f" {wl} W ←── │    +    │ ──→ E {el}",
        f"         └────{sl}────┘",
        f"              ↑  S",
        f"              {_q(S)}",
        "",
        f"  W queue: {_q(W)}   E queue: {_q(E)}",
    ]
    return "\n".join(lines)


# ── Textual app ───────────────────────────────────────────────────────────────

class IntersectionWidget(Static):
    """ASCII intersection display."""

    lights: reactive[dict] = reactive({d: LightPhase.RED for d in Direction})
    queues: reactive[dict] = reactive({d.value: 0 for d in Direction})

    def render(self) -> str:  # type: ignore[override]
        lmap = {d: self.lights.get(d, LightPhase.RED) for d in Direction}
        qmap = {d: self.queues.get(d.value, 0) for d in Direction}
        return render_intersection(lmap, qmap)


class KPITable(Static):
    """Live KPI panel."""

    tick: reactive[int] = reactive(0)
    passed: reactive[int] = reactive(0)
    avg_wait: reactive[float] = reactive(0.0)
    throughput: reactive[float] = reactive(0.0)
    null_pct: reactive[float] = reactive(0.0)
    algorithm: reactive[str] = reactive("—")

    def render(self) -> str:  # type: ignore[override]
        return (
            f"[bold cyan]Tick:[/]        {self.tick:>6}\n"
            f"[bold cyan]Passed:[/]      {self.passed:>6}\n"
            f"[bold cyan]Avg wait:[/]    {self.avg_wait:>6.1f} ticks\n"
            f"[bold cyan]Throughput:[/]  {self.throughput:>6.1f} /100t\n"
            f"[bold cyan]Null ctrl:[/]   {self.null_pct:>5.1f}%\n"
            f"[bold cyan]Algorithm:[/]   [bold yellow]{self.algorithm}[/]\n"
        )


class CrossroadsTUI(App):
    """Live crossroads simulation TUI using Textual."""

    TITLE = "Crossroads Simulator"
    SUB_TITLE = "Python-native TUI showcase"

    CSS = """
    Screen { layout: vertical; }

    #top { height: 1fr; layout: horizontal; }
    #intersection-panel { width: 50; border: solid $primary; padding: 1 2; }
    #kpi-panel { width: 30; border: solid $success; padding: 1 2; }
    #right-panel { width: 1fr; layout: vertical; }
    #light-panel { height: 10; border: solid $warning; padding: 0 1; }
    #safety-log { height: 1fr; border: solid $error; }
    #controls { height: 3; layout: horizontal; padding: 0 1; }
    """

    BINDINGS = [
        Binding("s", "start", "Start"),
        Binding("p", "stop", "Pause"),
        Binding("r", "restart", "Restart"),
        Binding("1", "algo_fixed", "Fixed"),
        Binding("2", "algo_adaptive", "Adaptive"),
        Binding("3", "algo_null", "Null"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._engine: SimEngine | None = None
        self._switcher: AlgorithmSwitcher | None = None
        self._algo = "fixed_cycle"
        self._tick_thread: threading.Thread | None = None
        self._running = threading.Event()
        self._lock = threading.Lock()
        self._kpi_history: deque[dict] = deque(maxlen=200)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top"):
            with Vertical(id="intersection-panel"):
                yield Label("[bold]Intersection[/]")
                yield IntersectionWidget(id="ix")
            with Vertical(id="kpi-panel"):
                yield Label("[bold]KPI[/]")
                yield KPITable(id="kpi")
            with Vertical(id="right-panel"):
                yield Label("[bold]Traffic Lights[/]", id="light-label")
                yield DataTable(id="light-table")
                yield Label("[bold]Safety Log[/]")
                yield RichLog(id="safety-log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        tbl = self.query_one("#light-table", DataTable)
        tbl.add_columns("Direction", "Phase", "Ticks in phase")
        self._reset_engine()
        self.set_interval(0.15, self._tick_and_refresh)

    def _reset_engine(self) -> None:
        with self._lock:
            self._running.clear()
            cfg = SimConfig(seed=42, max_ticks=None, algorithm=self._algo, tick_step_ms=150)
            ix = Intersection()
            self._switcher = AlgorithmSwitcher(self._algo)
            self._engine = SimEngine(cfg, ix, self._switcher, SafetyChecker())
            self._engine.add_listener(self._on_event)

    def _on_event(self, event) -> None:
        from sim.enums import EventType
        if event.event_type == EventType.SAFETY_OVERRIDE:
            log = self.query_one("#safety-log", RichLog)
            rule = event.payload.get("rule", "?")
            expl = event.payload.get("explanation", "")[:80]
            log.write(f"[bold red][T{event.tick}][/] {rule}: {expl}")

    def _tick_and_refresh(self) -> None:
        if self._engine and self._running.is_set():
            with self._lock:
                kpi = self._engine.step()
                if kpi:
                    self._kpi_history.append({
                        "tick": kpi.tick,
                        "passed": kpi.vehicles_passed,
                        "avg_wait": kpi.avg_wait_ticks,
                        "throughput": kpi.throughput_per_100_ticks,
                        "null_pct": kpi.pct_null_control,
                    })
            self._refresh_ui()

    def _refresh_ui(self) -> None:
        if not self._engine:
            return
        eng = self._engine
        ix = eng.intersection

        # Intersection widget
        lights_map = {d: ix.lights[d].phase for d in Direction}
        queues_map = {d.value: ix.lanes[d].queue_length for d in Direction}
        iw = self.query_one("#ix", IntersectionWidget)
        iw.lights = lights_map
        iw.queues = queues_map

        # KPI
        kpi_w = self.query_one("#kpi", KPITable)
        kpi_w.tick = eng.tick
        if self._kpi_history:
            last = self._kpi_history[-1]
            kpi_w.passed = last["passed"]
            kpi_w.avg_wait = last["avg_wait"]
            kpi_w.throughput = last["throughput"]
            kpi_w.null_pct = last["null_pct"]
        kpi_w.algorithm = self._algo

        # Light table
        tbl = self.query_one("#light-table", DataTable)
        tbl.clear()
        for d in Direction:
            lt = ix.lights[d]
            tbl.add_row(
                d.value.upper(),
                _phase_str(lt.phase),
                str(lt.ticks_in_phase),
            )

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_start(self) -> None:
        if self._engine:
            self._engine.start()
            self._running.set()

    def action_stop(self) -> None:
        self._running.clear()

    def action_restart(self) -> None:
        self._reset_engine()
        self.query_one("#safety-log", RichLog).clear()
        self._kpi_history.clear()

    def action_algo_fixed(self) -> None:
        self._algo = "fixed_cycle"
        if self._switcher:
            self._switcher.request_switch("fixed_cycle")

    def action_algo_adaptive(self) -> None:
        self._algo = "adaptive_cycle"
        if self._switcher:
            self._switcher.request_switch("adaptive_cycle")

    def action_algo_null(self) -> None:
        self._algo = "null_control"
        if self._switcher:
            self._switcher.request_switch("null_control")


def main() -> None:
    app = CrossroadsTUI()
    app.run()


if __name__ == "__main__":
    main()
