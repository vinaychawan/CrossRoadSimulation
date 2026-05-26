"""
Crossroads Simulation — Python Showcase Launcher

Launches one of three showcase modes:
  gui        PyQt6 animated GUI with live charts          (interactive)
  tui        Textual terminal dashboard                    (interactive)
  analytics  matplotlib + pandas multi-algo analysis      (interactive)
  headless   Pure Python console demo with rich output    (non-interactive)

Usage:
    python3 -m showcase                   # interactive menu
    python3 -m showcase gui
    python3 -m showcase tui
    python3 -m showcase analytics
    python3 -m showcase headless
"""
from __future__ import annotations

import sys


def _menu() -> str:
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║       CROSSROADS SIMULATOR — Python Showcase         ║")
    print("╠══════════════════════════════════════════════════════╣")
    print("║  1. gui        PyQt6 animated GUI + live charts      ║")
    print("║  2. tui        Textual terminal dashboard            ║")
    print("║  3. analytics  matplotlib + pandas analysis           ║")
    print("║  4. headless   Console demo (rich output)            ║")
    print("║  q. quit                                             ║")
    print("╚══════════════════════════════════════════════════════╝")
    return input("  Choose [1/2/3/4/q]: ").strip().lower()


def _launch_gui() -> None:
    from showcase.gui import main
    main()


def _launch_tui() -> None:
    from showcase.tui import main
    main()


def _launch_analytics() -> None:
    from showcase.analytics import main
    main()


def _launch_headless() -> None:
    from showcase.headless import main
    main()


_MAP = {
    "1": _launch_gui,    "gui": _launch_gui,
    "2": _launch_tui,    "tui": _launch_tui,
    "3": _launch_analytics, "analytics": _launch_analytics,
    "4": _launch_headless,  "headless": _launch_headless,
}


def main() -> None:
    choice = sys.argv[1] if len(sys.argv) > 1 else _menu()
    fn = _MAP.get(choice)
    if fn is None or choice in ("q", "quit"):
        print("Bye!")
        return
    fn()


if __name__ == "__main__":
    main()
