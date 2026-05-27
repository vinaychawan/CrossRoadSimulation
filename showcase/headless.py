"""
Headless console showcase using the `rich` library.

Runs a sequence of demonstrations with live terminal output:
  1. Fixed-cycle run with live progress
  2. Algorithm comparison table
  3. 10-seed Monte Carlo what-if
  4. Safety checker demonstration
  5. Event log inspection

Run with:
    python3 -m showcase.headless
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from rich import print as rprint

import algorithms
from algorithms.switcher import AlgorithmSwitcher
from safety.checker import SafetyChecker
from sim.engine import SimConfig, SimEngine
from sim.enums import Direction, LightPhase
from sim.intersection import Intersection

algorithms.discover()

console = Console()

_PHASE_STYLE = {
    LightPhase.GREEN: "bold green",
    LightPhase.YELLOW: "bold yellow",
    LightPhase.RED: "bold red",
    LightPhase.AMBER_FLASH: "bold dark_orange blink",
}
_PHASE_ICON = {
    LightPhase.GREEN: "●", LightPhase.YELLOW: "◑",
    LightPhase.RED: "○", LightPhase.AMBER_FLASH: "◈",
}


def _phase_cell(phase: LightPhase) -> Text:
    icon = _PHASE_ICON[phase]
    return Text(f"{icon} {phase.value.upper()}", style=_PHASE_STYLE[phase])


def _run_sim(algo: str, seed: int, max_ticks: int):
    cfg = SimConfig(seed=seed, algorithm=algo, max_ticks=max_ticks)
    ix = Intersection()
    eng = SimEngine(cfg, ix, AlgorithmSwitcher(algo), SafetyChecker())
    eng.start()
    kpi_samples = []
    while eng.running:
        kpi = eng.step()
        if kpi:
            kpi_samples.append(kpi)
    final = eng._kpi.snapshot(eng.tick, ix, eng._active_vehicles)
    return final, kpi_samples, eng


# ── Demo 1: Live intersection viewer ──────────────────────────────────────────

def demo_live_run():
    console.rule("[bold cyan]Demo 1 — Live Intersection State[/]")
    console.print("[dim]Running fixed_cycle seed=42 for 120 ticks with live display…[/]\n")

    cfg = SimConfig(seed=42, algorithm="fixed_cycle", max_ticks=120)
    ix = Intersection()
    eng = SimEngine(cfg, ix, AlgorithmSwitcher("fixed_cycle"), SafetyChecker())
    eng.start()

    def _make_table() -> Table:
        tbl = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan",
                    border_style="blue")
        tbl.add_column("Tick", width=6, justify="right")
        for d in Direction:
            tbl.add_column(d.value.upper(), width=14)
        tbl.add_column("Queues", width=20)
        return tbl

    last_rows: list[tuple] = []
    DISPLAY_ROWS = 8

    def _build_panel() -> Panel:
        tbl = _make_table()
        for row in last_rows[-DISPLAY_ROWS:]:
            tbl.add_row(*row)
        return Panel(tbl, title="[bold]Intersection State[/]", border_style="cyan")

    with Live(_build_panel(), refresh_per_second=10, console=console) as live:
        while eng.running:
            eng.step()
            lights = {d: ix.lights[d].phase for d in Direction}
            queues = {d: ix.lanes[d].queue_length for d in Direction}
            row = (
                str(eng.tick),
                *[_phase_cell(lights[d]) for d in Direction],
                " ".join(f"{d.value[0].upper()}:{queues[d]}" for d in Direction),
            )
            last_rows.append(row)
            live.update(_build_panel())
            time.sleep(0.02)

    final = eng._kpi.snapshot(eng.tick, ix, eng._active_vehicles)
    console.print(f"\n[green]✓ Done.[/] Passed={final.vehicles_passed} "
                  f"AvgWait={final.avg_wait_ticks:.1f} "
                  f"Throughput={final.throughput_per_100_ticks:.1f}/100t\n")


# ── Demo 2: Algorithm comparison table ───────────────────────────────────────

def demo_algorithm_comparison():
    console.rule("[bold cyan]Demo 2 — Algorithm Comparison[/]")
    algos = algorithms.available()
    seeds = list(range(6))
    rows = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as prog:
        task = prog.add_task("Running simulations…", total=len(algos) * len(seeds))
        for algo in algos:
            for seed in seeds:
                final, _, _ = _run_sim(algo, seed, max_ticks=300)
                rows.append({
                    "algorithm": algo, "seed": seed,
                    "passed": final.vehicles_passed,
                    "avg_wait": final.avg_wait_ticks,
                    "null_pct": final.pct_null_control,
                })
                prog.advance(task)

    df = pd.DataFrame(rows)
    summary = df.groupby("algorithm").agg(
        passed_mean=("passed", "mean"),
        passed_std=("passed", "std"),
        wait_mean=("avg_wait", "mean"),
        wait_std=("avg_wait", "std"),
        null_mean=("null_pct", "mean"),
    ).round(2)

    tbl = Table(title="Algorithm KPI Summary", box=box.DOUBLE_EDGE,
                header_style="bold magenta", border_style="magenta")
    tbl.add_column("Algorithm", style="bold")
    tbl.add_column("Passed (mean±std)", justify="right")
    tbl.add_column("Avg Wait (mean±std)", justify="right")
    tbl.add_column("Null%", justify="right")
    tbl.add_column("Winner 🏆", justify="center")

    best_thr = summary["passed_mean"].idxmax()
    best_wait = summary["wait_mean"].idxmin()

    for algo in sorted(summary.index):
        row = summary.loc[algo]
        badges = []
        if algo == best_thr:
            badges.append("[bold green]throughput[/]")
        if algo == best_wait:
            badges.append("[bold cyan]min-wait[/]")
        tbl.add_row(
            algo.replace("_", " "),
            f"{row.passed_mean:.1f} ± {row.passed_std:.1f}",
            f"{row.wait_mean:.1f} ± {row.wait_std:.1f}",
            f"{row.null_mean:.1f}%",
            " ".join(badges) if badges else "—",
        )

    console.print(tbl)
    console.print()


# ── Demo 3: Monte Carlo what-if ───────────────────────────────────────────────

def demo_whatif():
    console.rule("[bold cyan]Demo 3 — Monte Carlo What-If (10 seeds)[/]")
    algos = algorithms.available()

    for algo in algos:
        waits, throughputs, nulls = [], [], []
        for seed in range(10):
            final, _, _ = _run_sim(algo, seed, max_ticks=400)
            waits.append(final.avg_wait_ticks)
            throughputs.append(final.throughput_per_100_ticks)
            nulls.append(final.pct_null_control)

        wa = np.array(waits)
        ta = np.array(throughputs)

        panels = [
            Panel(
                f"[bold]mean:[/] {wa.mean():.2f}\n"
                f"[bold]std: [/] {wa.std():.2f}\n"
                f"[bold]p95: [/] {np.percentile(wa, 95):.2f}\n"
                f"[bold]min: [/] {wa.min():.2f}",
                title="Avg Wait (ticks)", border_style="blue"
            ),
            Panel(
                f"[bold]mean:[/] {ta.mean():.2f}\n"
                f"[bold]std: [/] {ta.std():.2f}\n"
                f"[bold]p95: [/] {np.percentile(ta, 95):.2f}\n"
                f"[bold]min: [/] {ta.min():.2f}",
                title="Throughput / 100t", border_style="green"
            ),
        ]
        console.print(Panel(Columns(panels), title=f"[bold yellow]{algo}[/]",
                            border_style="yellow"))

    console.print()


# ── Demo 4: Safety checker walk-through ───────────────────────────────────────

def demo_safety():
    console.rule("[bold cyan]Demo 4 — Safety Checker[/]")
    from sim.enums import LightPhase as LP
    checker = SafetyChecker(all_red_intergreen_ticks=4)
    ix = Intersection()

    cases = [
        ("R1 — Conflicting greens (N+E)",
         {Direction.NORTH: LP.GREEN, Direction.EAST: LP.GREEN,
          Direction.SOUTH: LP.RED, Direction.WEST: LP.RED}),
        ("R1 — Valid NS green",
         {Direction.NORTH: LP.GREEN, Direction.SOUTH: LP.GREEN,
          Direction.EAST: LP.RED, Direction.WEST: LP.RED}),
    ]

    tbl = Table(title="Safety Checker Results", box=box.SIMPLE_HEAD,
                header_style="bold red", border_style="red")
    tbl.add_column("Test case", width=30)
    tbl.add_column("Result", width=14)
    tbl.add_column("Rule fired", width=22)
    tbl.add_column("Explanation", width=60)

    for label, cmds in cases:
        # First call primes the checker (startup — never been green)
        safe, violations = checker.check(cmds, ix)
        if violations:
            v = violations[0]
            tbl.add_row(label, "[bold red]OVERRIDE[/]", v["rule"], v["explanation"][:60])
        else:
            tbl.add_row(label, "[bold green]SAFE[/]", "—", "Commands passed through unchanged")

    # Prime and re-check for R2
    good_cmd = {Direction.NORTH: LP.GREEN, Direction.SOUTH: LP.GREEN,
                Direction.EAST: LP.RED, Direction.WEST: LP.RED}
    checker.check(good_cmd, ix)  # prime ever_been_green

    bad_r2 = {Direction.NORTH: LP.GREEN, Direction.SOUTH: LP.GREEN,
              Direction.EAST: LP.RED, Direction.WEST: LP.RED}
    safe2, v2 = checker.check(bad_r2, ix)
    if v2:
        tbl.add_row("R2 — RED→GREEN too soon (after prime)",
                    "[bold red]OVERRIDE[/]", v2[0]["rule"], v2[0]["explanation"][:60])

    console.print(tbl)
    console.print(f"  [dim]Total checker interventions: {checker.total_interventions}[/]\n")


# ── Demo 5: Event log inspection ─────────────────────────────────────────────

def demo_event_log():
    console.rule("[bold cyan]Demo 5 — Event Log & Determinism[/]")
    from sim.enums import EventType

    final, samples, eng = _run_sim("fixed_cycle", 99, 100)
    events = eng.event_log.all_events()

    # Summarise by type
    from collections import Counter
    counts = Counter(e.event_type.value for e in events)

    tbl = Table(title="Event Log Summary (seed=99, 100 ticks)", box=box.MINIMAL_DOUBLE_HEAD,
                header_style="bold cyan")
    tbl.add_column("Event Type", style="bold")
    tbl.add_column("Count", justify="right")
    for etype, count in sorted(counts.items(), key=lambda x: -x[1]):
        tbl.add_row(etype, str(count))
    tbl.add_row("[bold]TOTAL[/]", f"[bold]{len(events)}[/]")
    console.print(tbl)

    # Determinism check
    cs1 = eng.event_log.checksum()
    final2, _, eng2 = _run_sim("fixed_cycle", 99, 100)
    cs2 = eng2.event_log.checksum()

    match = cs1 == cs2
    console.print(
        f"\n  Checksum run 1: [cyan]{cs1[:24]}…[/]\n"
        f"  Checksum run 2: [cyan]{cs2[:24]}…[/]\n"
        f"  Deterministic:  {'[bold green]YES ✓[/]' if match else '[bold red]NO ✗[/]'}\n"
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    console.print()
    console.print(Panel.fit(
        "[bold white]Crossroads Simulation[/]\n"
        "[dim]Python-only showcase: rich · numpy · pandas · matplotlib[/]",
        border_style="bright_blue",
    ))
    console.print()

    demo_live_run()
    demo_algorithm_comparison()
    demo_whatif()
    demo_safety()
    demo_event_log()

    console.print(Panel.fit(
        "[bold green]All demos complete![/]\n\n"
        "[dim]Run [bold]python3 -m showcase gui[/][dim] for the PyQt6 interactive GUI\n"
        "Run [bold]python3 -m showcase tui[/][dim] for the Textual terminal dashboard\n"
        "Run [bold]python3 -m showcase analytics[/][dim] for the matplotlib charts[/]",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
