"""
Post-run analytics showcase using matplotlib, numpy, and pandas.

Runs N simulation seeds for each algorithm, collects KPI data,
and produces a multi-panel matplotlib figure + console summary.

Run with:
    python3 -m showcase.analytics
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass

import matplotlib
try:
    matplotlib.use("TkAgg" if sys.platform != "linux" else "Qt5Agg")
except Exception:
    pass
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd

try:
    matplotlib.use("QtAgg")
except Exception:
    pass

import algorithms
from algorithms.switcher import AlgorithmSwitcher
from safety.checker import SafetyChecker
from sim.engine import SimConfig, SimEngine
from sim.enums import Direction, EventType
from sim.intersection import Intersection

algorithms.discover()

# ── Colour palette ────────────────────────────────────────────────────────────
_PALETTE = {
    "fixed_cycle":    "#42a5f5",
    "adaptive_cycle": "#66bb6a",
    "null_control":   "#ef5350",
}
_DEFAULT_COLOR = "#aaaaaa"
_BG = "#1a2a35"
_GRID = "#2d3f4c"
_TEXT = "#eceff1"


def _palette(algo: str) -> str:
    return _PALETTE.get(algo, _DEFAULT_COLOR)


# ── Run a single headless simulation ─────────────────────────────────────────

@dataclass
class RunResult:
    algorithm: str
    seed: int
    ticks: list[int]
    avg_waits: list[float]
    throughputs: list[float]
    null_pcts: list[float]
    vehicles_passed: int
    final_avg_wait: float
    pct_null_control: float


def run_sim(algorithm: str, seed: int, max_ticks: int = 400) -> RunResult:
    cfg = SimConfig(seed=seed, algorithm=algorithm, max_ticks=max_ticks)
    ix = Intersection()
    eng = SimEngine(cfg, ix, AlgorithmSwitcher(algorithm), SafetyChecker())
    eng.start()

    ticks, avg_waits, throughputs, null_pcts = [], [], [], []

    def _on_event(event):
        if event.event_type == EventType.KPI_SAMPLE:
            pass  # we collect inline below

    while eng.running:
        kpi = eng.step()
        if kpi:
            ticks.append(kpi.tick)
            avg_waits.append(kpi.avg_wait_ticks)
            throughputs.append(kpi.throughput_per_100_ticks)
            null_pcts.append(kpi.pct_null_control)

    final = eng._kpi.snapshot(eng.tick, ix, eng._active_vehicles)

    return RunResult(
        algorithm=algorithm,
        seed=seed,
        ticks=ticks,
        avg_waits=avg_waits,
        throughputs=throughputs,
        null_pcts=null_pcts,
        vehicles_passed=final.vehicles_passed,
        final_avg_wait=final.avg_wait_ticks,
        pct_null_control=final.pct_null_control,
    )


# ── Collect multi-seed results ────────────────────────────────────────────────

def collect_results(algos: list[str], n_seeds: int = 8, max_ticks: int = 400) -> list[RunResult]:
    results = []
    total = len(algos) * n_seeds
    print(f"\nRunning {total} simulations ({len(algos)} algorithms × {n_seeds} seeds × {max_ticks} ticks)…")
    for algo in algos:
        for seed in range(n_seeds):
            r = run_sim(algo, seed, max_ticks)
            results.append(r)
            sys.stdout.write(
                f"  [{algo[:12]:12s}] seed={seed}  passed={r.vehicles_passed:3d}  "
                f"avg_wait={r.final_avg_wait:5.1f}  null%={r.pct_null_control:5.1f}\n"
            )
            sys.stdout.flush()
    return results


# ── Build pandas DataFrame ────────────────────────────────────────────────────

def to_dataframe(results: list[RunResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "algorithm": r.algorithm,
            "seed": r.seed,
            "vehicles_passed": r.vehicles_passed,
            "avg_wait_ticks": r.final_avg_wait,
            "pct_null_control": r.pct_null_control,
        })
    return pd.DataFrame(rows)


# ── Plot ──────────────────────────────────────────────────────────────────────

def _style_ax(ax, title: str = "", xlabel: str = "", ylabel: str = "") -> None:
    ax.set_facecolor(_BG)
    ax.set_title(title, color=_TEXT, fontsize=10, pad=6)
    ax.set_xlabel(xlabel, color=_TEXT, fontsize=8)
    ax.set_ylabel(ylabel, color=_TEXT, fontsize=8)
    ax.tick_params(colors=_TEXT, labelsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor(_GRID)
    ax.grid(color=_GRID, linestyle="--", linewidth=0.5, alpha=0.7)
    ax.xaxis.label.set_color(_TEXT)
    ax.yaxis.label.set_color(_TEXT)


def build_figure(results: list[RunResult], df: pd.DataFrame) -> plt.Figure:
    algos = sorted(set(r.algorithm for r in results))

    fig = plt.figure(figsize=(16, 10), facecolor=_BG)
    fig.suptitle("Crossroads Simulation — Algorithm Comparison", color=_TEXT,
                 fontsize=14, fontweight="bold", y=0.98)

    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.35,
                           left=0.07, right=0.97, top=0.93, bottom=0.06)

    # ── Panel 1: Throughput time-series (first seed per algo) ─────────────
    ax1 = fig.add_subplot(gs[0, :2])
    _style_ax(ax1, "Throughput over time (seed=0)", "Tick", "vehicles / 100 ticks")
    for algo in algos:
        r0 = next(r for r in results if r.algorithm == algo and r.seed == 0)
        if r0.ticks:
            ax1.plot(r0.ticks, r0.throughputs, color=_palette(algo),
                     label=algo.replace("_", " "), linewidth=1.5)
    ax1.legend(fontsize=7, facecolor=_GRID, labelcolor=_TEXT, framealpha=0.8)

    # ── Panel 2: Avg wait time-series ─────────────────────────────────────
    ax2 = fig.add_subplot(gs[1, :2])
    _style_ax(ax2, "Avg Wait over time (seed=0)", "Tick", "avg wait (ticks)")
    for algo in algos:
        r0 = next(r for r in results if r.algorithm == algo and r.seed == 0)
        if r0.ticks:
            ax2.plot(r0.ticks, r0.avg_waits, color=_palette(algo),
                     label=algo.replace("_", " "), linewidth=1.5)
    ax2.legend(fontsize=7, facecolor=_GRID, labelcolor=_TEXT, framealpha=0.8)

    # ── Panel 3: Null% time-series ────────────────────────────────────────
    ax3 = fig.add_subplot(gs[2, :2])
    _style_ax(ax3, "Null Control % over time (seed=0)", "Tick", "null ctrl %")
    for algo in algos:
        r0 = next(r for r in results if r.algorithm == algo and r.seed == 0)
        if r0.ticks:
            ax3.plot(r0.ticks, r0.null_pcts, color=_palette(algo),
                     label=algo.replace("_", " "), linewidth=1.5)
    ax3.legend(fontsize=7, facecolor=_GRID, labelcolor=_TEXT, framealpha=0.8)

    # ── Panel 4: Vehicles passed box plot ─────────────────────────────────
    ax4 = fig.add_subplot(gs[0, 2])
    _style_ax(ax4, "Vehicles Passed", "Algorithm", "count")
    data_passed = [df[df.algorithm == a]["vehicles_passed"].values for a in algos]
    bp = ax4.boxplot(data_passed, patch_artist=True, notch=False,
                     medianprops={"color": "#ffffff", "linewidth": 2})
    for patch, algo in zip(bp["boxes"], algos):
        patch.set_facecolor(_palette(algo))
        patch.set_alpha(0.7)
    for el in ["whiskers", "caps", "fliers"]:
        for line in bp[el]:
            line.set_color(_TEXT)
    ax4.set_xticks(range(1, len(algos) + 1))
    ax4.set_xticklabels([a.replace("_cycle", "").replace("_control", "") for a in algos],
                        rotation=15, ha="right", fontsize=7)

    # ── Panel 5: Avg wait violin plot ─────────────────────────────────────
    ax5 = fig.add_subplot(gs[1, 2])
    _style_ax(ax5, "Avg Wait Distribution", "Algorithm", "ticks")
    data_wait = [df[df.algorithm == a]["avg_wait_ticks"].values for a in algos]
    vp = ax5.violinplot(data_wait, showmedians=True, showextrema=True)
    for i, (body, algo) in enumerate(zip(vp["bodies"], algos)):
        body.set_facecolor(_palette(algo))
        body.set_alpha(0.7)
    vp["cmedians"].set_color("#ffffff")
    vp["cmaxes"].set_color(_TEXT)
    vp["cmins"].set_color(_TEXT)
    vp["cbars"].set_color(_TEXT)
    ax5.set_xticks(range(1, len(algos) + 1))
    ax5.set_xticklabels([a.replace("_cycle", "").replace("_control", "") for a in algos],
                        rotation=15, ha="right", fontsize=7)

    # ── Panel 6: Radar / stats table ─────────────────────────────────────
    ax6 = fig.add_subplot(gs[2, 2])
    ax6.set_facecolor(_BG)
    ax6.axis("off")
    ax6.set_title("Summary Statistics", color=_TEXT, fontsize=10, pad=6)

    summary = df.groupby("algorithm").agg(
        passed_mean=("vehicles_passed", "mean"),
        wait_mean=("avg_wait_ticks", "mean"),
        null_mean=("pct_null_control", "mean"),
    ).round(1)

    col_labels = ["Algorithm", "Passed\n(mean)", "Wait\n(mean)", "Null%\n(mean)"]
    table_data = []
    for algo in algos:
        row = summary.loc[algo]
        table_data.append([
            algo.replace("_", " "),
            f"{row.passed_mean:.1f}",
            f"{row.wait_mean:.1f}",
            f"{row.null_mean:.1f}%",
        ])

    tbl = ax6.table(
        cellText=table_data,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1.1, 1.6)
    for (row, col), cell in tbl.get_celld().items():
        cell.set_facecolor(_GRID if row == 0 else _BG)
        cell.set_text_props(color=_TEXT)
        cell.set_edgecolor(_GRID)
        if row > 0:
            algo = algos[row - 1]
            cell.set_facecolor(_palette(algo) + "33")

    return fig


# ── Console summary ───────────────────────────────────────────────────────────

def print_summary(df: pd.DataFrame) -> None:
    print("\n" + "═" * 62)
    print("  ALGORITHM COMPARISON SUMMARY")
    print("═" * 62)
    summary = df.groupby("algorithm").agg(
        seeds=("seed", "count"),
        passed_mean=("vehicles_passed", "mean"),
        passed_std=("vehicles_passed", "std"),
        wait_mean=("avg_wait_ticks", "mean"),
        wait_std=("avg_wait_ticks", "std"),
        null_mean=("pct_null_control", "mean"),
    ).round(2)
    print(summary.to_string())
    print("═" * 62)

    best_thr = summary["passed_mean"].idxmax()
    best_wait = summary["wait_mean"].idxmin()
    print(f"\n  ★  Best throughput : {best_thr}")
    print(f"  ★  Lowest avg wait  : {best_wait}")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main(show: bool = True) -> plt.Figure:
    algos = algorithms.available()
    results = collect_results(algos, n_seeds=6, max_ticks=300)
    df = to_dataframe(results)
    print_summary(df)

    fig = build_figure(results, df)
    if show:
        plt.show()
    return fig


if __name__ == "__main__":
    main()
