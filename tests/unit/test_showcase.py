"""
Showcase tests — 100% coverage of showcase/*.py.
Uses mocking to avoid GUI/TUI display and plt.show().
"""
import importlib
import sys
from unittest import mock

import pytest

# ── __main__ ─────────────────────────────────────────────────────────────────

class TestMain:
    def _get_main(self):
        # Reload to get fresh module
        import showcase.__main__ as m
        importlib.reload(m)
        return m

    def test_main_quit_by_choice(self):
        m = self._get_main()
        with mock.patch("sys.argv", ["showcase"]):
            with mock.patch("builtins.input", return_value="q"):
                m.main()  # should print "Bye!" and return

    def test_main_quit_keyword(self):
        m = self._get_main()
        with mock.patch("sys.argv", ["showcase"]):
            with mock.patch("builtins.input", return_value="quit"):
                m.main()

    def test_main_unknown_choice(self):
        m = self._get_main()
        with mock.patch("sys.argv", ["showcase"]):
            with mock.patch("builtins.input", return_value="zzz"):
                m.main()  # unknown → fn is None, prints Bye

    def test_main_dispatch_headless(self):
        m = self._get_main()
        mock_fn = mock.MagicMock()
        with mock.patch("sys.argv", ["showcase", "headless"]):
            with mock.patch.dict(m._MAP, {"headless": mock_fn, "4": mock_fn}):
                m.main()
                mock_fn.assert_called_once()

    def test_main_dispatch_gui(self):
        m = self._get_main()
        mock_fn = mock.MagicMock()
        with mock.patch("sys.argv", ["showcase", "gui"]):
            with mock.patch.dict(m._MAP, {"gui": mock_fn, "1": mock_fn}):
                m.main()
                mock_fn.assert_called_once()

    def test_main_dispatch_tui(self):
        m = self._get_main()
        mock_fn = mock.MagicMock()
        with mock.patch("sys.argv", ["showcase", "tui"]):
            with mock.patch.dict(m._MAP, {"tui": mock_fn, "2": mock_fn}):
                m.main()
                mock_fn.assert_called_once()

    def test_main_dispatch_analytics(self):
        m = self._get_main()
        mock_fn = mock.MagicMock()
        with mock.patch("sys.argv", ["showcase", "analytics"]):
            with mock.patch.dict(m._MAP, {"analytics": mock_fn, "3": mock_fn}):
                m.main()
                mock_fn.assert_called_once()

    def test_main_dispatch_numeric_1(self):
        m = self._get_main()
        mock_fn = mock.MagicMock()
        with mock.patch("sys.argv", ["showcase", "1"]):
            with mock.patch.dict(m._MAP, {"gui": mock_fn, "1": mock_fn}):
                m.main()
                mock_fn.assert_called_once()

    def test_main_dispatch_numeric_4(self):
        m = self._get_main()
        mock_fn = mock.MagicMock()
        with mock.patch("sys.argv", ["showcase", "4"]):
            with mock.patch.dict(m._MAP, {"headless": mock_fn, "4": mock_fn}):
                m.main()
                mock_fn.assert_called_once()

    def test_launch_functions_delegate(self):
        m = self._get_main()
        for attr in ("_launch_gui", "_launch_tui", "_launch_analytics", "_launch_headless"):
            fn = getattr(m, attr)
            # Should be callable
            assert callable(fn)

    def test_launch_headless_calls_main(self):
        m = self._get_main()
        with mock.patch("showcase.headless.main") as mock_main:
            m._launch_headless()
            mock_main.assert_called_once()

    def test_launch_analytics_calls_main(self):
        m = self._get_main()
        with mock.patch("showcase.analytics.main") as mock_main:
            m._launch_analytics()
            mock_main.assert_called_once()

    def test_launch_gui_calls_main(self):
        m = self._get_main()
        import showcase.gui as gui_module
        with mock.patch.object(gui_module, "main") as mock_main:
            m._launch_gui()
            mock_main.assert_called_once()

    def test_launch_tui_calls_main(self):
        m = self._get_main()
        import showcase.tui as tui_module
        with mock.patch.object(tui_module, "main") as mock_main:
            m._launch_tui()
            mock_main.assert_called_once()

    def test_menu_prints_and_returns_input(self, monkeypatch):
        m = self._get_main()
        monkeypatch.setattr("builtins.input", lambda _: "q")
        result = m._menu()
        assert result == "q"


# ── analytics.py ─────────────────────────────────────────────────────────────

class TestAnalytics:
    @pytest.fixture(autouse=True)
    def patch_matplotlib(self):
        """Prevent any actual display."""
        with mock.patch("matplotlib.pyplot.show"):
            yield

    def test_run_sim_returns_runresult(self):
        from showcase.analytics import run_sim
        result = run_sim("null_control", seed=0, max_ticks=20)
        assert result.algorithm == "null_control"
        assert result.seed == 0
        assert isinstance(result.vehicles_passed, int)
        assert isinstance(result.final_avg_wait, float)
        assert isinstance(result.pct_null_control, float)

    def test_run_sim_ticks_populated(self):
        from showcase.analytics import run_sim
        result = run_sim("fixed_cycle", seed=1, max_ticks=30)
        # ticks/throughputs/avg_waits are only populated at KPI sample intervals
        assert isinstance(result.ticks, list)
        assert isinstance(result.throughputs, list)

    def test_collect_results(self):
        from showcase.analytics import collect_results
        results = collect_results(["null_control"], n_seeds=2, max_ticks=10)
        assert len(results) == 2
        assert all(r.algorithm == "null_control" for r in results)

    def test_to_dataframe(self):
        import pandas as pd

        from showcase.analytics import run_sim, to_dataframe
        results = [run_sim("null_control", seed=i, max_ticks=10) for i in range(2)]
        df = to_dataframe(results)
        assert isinstance(df, pd.DataFrame)
        assert "algorithm" in df.columns
        assert "vehicles_passed" in df.columns
        assert len(df) == 2

    def test_print_summary(self, capsys):
        from showcase.analytics import print_summary, run_sim, to_dataframe
        results = [run_sim("null_control", seed=i, max_ticks=10) for i in range(2)]
        df = to_dataframe(results)
        print_summary(df)
        captured = capsys.readouterr()
        assert "null_control" in captured.out

    def test_build_figure(self):
        import matplotlib.pyplot as plt

        from showcase.analytics import build_figure, run_sim, to_dataframe
        results = [run_sim(a, seed=0, max_ticks=30)
                   for a in ("fixed_cycle", "adaptive_cycle", "null_control")]
        df = to_dataframe(results)
        fig = build_figure(results, df)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_main_no_show(self):
        """main(show=False) should return a Figure without calling plt.show."""
        import matplotlib.pyplot as plt

        from showcase import analytics
        with mock.patch("matplotlib.pyplot.show") as mock_show:
            fig = analytics.main(show=False)
        assert isinstance(fig, plt.Figure)
        mock_show.assert_not_called()
        plt.close(fig)


# ── headless.py ──────────────────────────────────────────────────────────────

class TestHeadless:
    """Test headless showcase helpers without live terminal output."""

    def test_phase_cell(self):
        from rich.text import Text

        from showcase.headless import _phase_cell
        from sim.enums import LightPhase
        t = _phase_cell(LightPhase.GREEN)
        assert isinstance(t, Text)
        assert "GREEN" in str(t)

    def test_run_sim_returns_kpi(self):
        from showcase.headless import _run_sim
        final, samples, eng = _run_sim("null_control", seed=0, max_ticks=20)
        assert hasattr(final, "vehicles_passed")
        assert isinstance(samples, list)
        assert eng is not None

    def test_demo_live_run_no_display(self):
        """demo_live_run runs without errors when Live is mocked."""
        from showcase import headless
        with mock.patch("rich.live.Live.__enter__", return_value=None), \
             mock.patch("rich.live.Live.__exit__", return_value=None), \
             mock.patch("rich.live.Live.update"), \
             mock.patch("time.sleep"):
            # Replace Live entirely
            mock_live = mock.MagicMock()
            mock_live.__enter__ = mock.Mock(return_value=mock_live)
            mock_live.__exit__ = mock.Mock(return_value=False)
            with mock.patch("showcase.headless.Live", return_value=mock_live):
                headless.demo_live_run()

    def test_demo_algorithm_comparison_no_display(self):
        """demo_algorithm_comparison runs without progress display."""
        from showcase import headless
        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.Mock(return_value=mock_progress)
        mock_progress.__exit__ = mock.Mock(return_value=False)
        mock_progress.add_task.return_value = "task"
        with mock.patch("showcase.headless.Progress", return_value=mock_progress), \
             mock.patch("showcase.headless.console"):
            headless.demo_algorithm_comparison()

    def test_demo_whatif_runs(self, capsys):
        from showcase import headless
        with mock.patch("showcase.headless.console"):
            headless.demo_whatif()

    def test_demo_safety_checker_runs(self):
        from showcase import headless
        with mock.patch("showcase.headless.console"):
            headless.demo_safety()

    def test_demo_event_log_runs(self):
        from showcase import headless
        with mock.patch("showcase.headless.console"):
            headless.demo_event_log()

    def test_main_no_prompts(self):
        from showcase import headless
        mock_console = mock.MagicMock()
        mock_live = mock.MagicMock()
        mock_live.__enter__ = mock.Mock(return_value=mock_live)
        mock_live.__exit__ = mock.Mock(return_value=False)
        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.Mock(return_value=mock_progress)
        mock_progress.__exit__ = mock.Mock(return_value=False)
        mock_progress.add_task.return_value = "task"
        with mock.patch("showcase.headless.console", mock_console), \
             mock.patch("showcase.headless.Live", return_value=mock_live), \
             mock.patch("showcase.headless.Progress", return_value=mock_progress), \
             mock.patch("time.sleep"):
            headless.main()


# ── tui.py ────────────────────────────────────────────────────────────────────
class TestGUI:
    """Tests for showcase/gui.py — uses PyQt6 fixtures with QApplication."""

    @pytest.fixture(scope="class")
    def qt_app(self):
        """Create a QApplication for the test class."""
        from PyQt6.QtWidgets import QApplication
        # QApplication may already exist (singleton)
        app = QApplication.instance() or QApplication(sys.argv)
        yield app

    def test_intersection_canvas_init(self, qt_app):
        from showcase.gui import IntersectionCanvas
        from sim.enums import LightPhase
        canvas = IntersectionCanvas()
        assert canvas._flash_state is True
        assert all(p == LightPhase.RED for p in canvas._lights.values())
        assert all(q == 0 for q in canvas._queues.values())

    def test_intersection_canvas_update_state(self, qt_app):
        from showcase.gui import IntersectionCanvas
        from sim.enums import Direction, LightPhase
        canvas = IntersectionCanvas()
        lights = {d.value: {"phase": "green"} for d in Direction}
        queues = {d.value: 3 for d in Direction}
        canvas.update_state(lights, queues, ["v1", "v2"])
        assert all(p == LightPhase.GREEN for p in canvas._lights.values())
        assert canvas._crossing == ["v1", "v2"]

    def test_intersection_canvas_toggle_flash(self, qt_app):
        from showcase.gui import IntersectionCanvas
        canvas = IntersectionCanvas()
        initial = canvas._flash_state
        canvas._toggle_flash()
        assert canvas._flash_state == (not initial)

    def test_live_chart_add_and_reset(self, qt_app):
        from PyQt6.QtGui import QColor

        from showcase.gui import LiveChart
        chart = LiveChart("Test", "units", QColor("#ffffff"))
        chart.add_point(1.0, 5.0)
        chart.add_point(2.0, 10.0)
        assert len(chart._points) == 2
        chart.reset()
        assert len(chart._points) == 0

    def test_live_chart_windowed(self, qt_app):
        from PyQt6.QtGui import QColor

        from showcase.gui import LiveChart
        chart = LiveChart("T", "u", QColor("#ffffff"))
        chart._window = 5
        for i in range(10):
            chart.add_point(float(i), float(i))
        assert len(chart._points) <= 5

    def test_main_window_init(self, qt_app):
        from showcase.gui import MainWindow
        win = MainWindow()
        assert win._engine is not None
        assert win._switcher is not None
        win.close()

    def test_main_window_new_engine(self, qt_app):
        from showcase.gui import MainWindow
        win = MainWindow()
        win._new_engine()
        assert win._engine is not None
        win.close()

    def test_main_window_start_stop(self, qt_app):
        from showcase.gui import MainWindow
        win = MainWindow()
        win._start()
        assert win._tick_timer.isActive()
        win._stop()
        assert not win._tick_timer.isActive()
        win.close()

    def test_main_window_reset(self, qt_app):
        from showcase.gui import MainWindow
        win = MainWindow()
        win._start()
        win._reset()
        assert not win._tick_timer.isActive()
        assert win._engine is not None
        win.close()

    def test_main_window_switch_algo(self, qt_app):
        from showcase.gui import MainWindow
        win = MainWindow()
        win._switch_algo("adaptive_cycle")
        win.close()

    def test_main_window_update_speed(self, qt_app):
        from showcase.gui import MainWindow
        win = MainWindow()
        win._start()
        win._update_speed(300)
        assert win._tick_timer.interval() == 300
        win._stop()
        win.close()

    def test_main_window_on_sim_event_safety(self, qt_app):
        from showcase.gui import MainWindow
        from sim.enums import EventType
        from sim.events import SimEvent
        win = MainWindow()
        evt = SimEvent(tick=1, event_type=EventType.SAFETY_OVERRIDE,
                       payload={"rule": "R1", "explanation": "conflict"})
        win._on_sim_event(evt)
        assert "R1" in win._safety_log.toPlainText()
        win.close()

    def test_main_window_on_sim_event_non_safety(self, qt_app):
        from showcase.gui import MainWindow
        from sim.enums import EventType
        from sim.events import SimEvent
        win = MainWindow()
        initial_text = win._safety_log.toPlainText()
        evt = SimEvent(tick=1, event_type=EventType.KPI_SAMPLE, payload={})
        win._on_sim_event(evt)
        assert win._safety_log.toPlainText() == initial_text
        win.close()

    def test_main_window_do_tick(self, qt_app):
        from showcase.gui import MainWindow
        win = MainWindow()
        win._engine.start()
        win._do_tick()
        assert win._engine.tick == 1
        win.close()

    def test_main_window_do_tick_no_engine(self, qt_app):
        from showcase.gui import MainWindow
        win = MainWindow()
        win._engine = None
        win._do_tick()  # should not raise
        win.close()

    def test_phase_color_dict(self, qt_app):
        from showcase.gui import _PHASE_COLOR
        from sim.enums import LightPhase
        assert set(_PHASE_COLOR.keys()) == set(LightPhase)

    def test_main_function_mocked(self):
        """Test main() by mocking QApplication and sys.exit."""
        with mock.patch("showcase.gui.QApplication") as MockApp, \
             mock.patch("sys.exit") as mock_exit:
            mock_instance = mock.MagicMock()
            MockApp.return_value = mock_instance
            mock_instance.exec.return_value = 0
            with mock.patch("showcase.gui.MainWindow") as MockWin:
                mock_win_instance = mock.MagicMock()
                MockWin.return_value = mock_win_instance
                from showcase import gui
                gui.main()
                mock_exit.assert_called_once_with(0)
class TestTUI:
    def test_phase_str_green(self):
        from showcase.tui import _phase_str
        from sim.enums import LightPhase
        s = _phase_str(LightPhase.GREEN)
        assert "GREEN" in s

    def test_phase_str_red(self):
        from showcase.tui import _phase_str
        from sim.enums import LightPhase
        s = _phase_str(LightPhase.RED)
        assert "RED" in s

    def test_phase_str_yellow(self):
        from showcase.tui import _phase_str
        from sim.enums import LightPhase
        s = _phase_str(LightPhase.YELLOW)
        assert "YELLOW" in s

    def test_phase_str_amber_flash(self):
        from showcase.tui import _phase_str
        from sim.enums import LightPhase
        s = _phase_str(LightPhase.AMBER_FLASH)
        assert "AMBER_FLASH" in s

    def test_render_intersection_returns_string(self):
        from showcase.tui import render_intersection
        from sim.enums import Direction, LightPhase
        lights = {d: LightPhase.RED for d in Direction}
        queues = {d: 0 for d in Direction}
        result = render_intersection(lights, queues)
        assert isinstance(result, str)
        assert "N" in result
        assert "S" in result

    def test_render_intersection_green_north(self):
        from showcase.tui import render_intersection
        from sim.enums import Direction, LightPhase
        lights = {Direction.NORTH: LightPhase.GREEN,
                  Direction.SOUTH: LightPhase.RED,
                  Direction.EAST: LightPhase.RED,
                  Direction.WEST: LightPhase.RED}
        queues = {d: 3 for d in Direction}
        result = render_intersection(lights, queues)
        assert isinstance(result, str)

    def test_render_intersection_all_phases(self):
        from showcase.tui import render_intersection
        from sim.enums import Direction, LightPhase
        phases = [LightPhase.GREEN, LightPhase.YELLOW, LightPhase.RED, LightPhase.AMBER_FLASH]
        dirs = list(Direction)
        lights = {dirs[i]: phases[i] for i in range(4)}
        queues = {d: i * 2 for i, d in enumerate(dirs)}
        result = render_intersection(lights, queues)
        assert isinstance(result, str)

    def test_intersection_widget_render(self):
        from showcase.tui import IntersectionWidget
        from sim.enums import Direction, LightPhase
        widget = IntersectionWidget()
        widget.lights = {d: LightPhase.GREEN for d in Direction}
        widget.queues = {d.value: 0 for d in Direction}
        result = widget.render()
        assert isinstance(result, str)

    def test_kpi_table_render(self):
        from showcase.tui import KPITable
        widget = KPITable()
        widget.tick = 10
        widget.passed = 5
        widget.avg_wait = 3.5
        widget.throughput = 12.4
        widget.null_pct = 0.0
        widget.algorithm = "fixed_cycle"
        result = widget.render()
        assert "10" in result
        assert "fixed_cycle" in result


# ── CrossroadsTUI logic (no event loop) ──────────────────────────────────────

class TestCrossroadsTUILogic:
    """Tests for CrossroadsTUI methods that don't need the Textual event loop."""

    @pytest.fixture
    def tui(self):
        from showcase.tui import CrossroadsTUI
        app = CrossroadsTUI.__new__(CrossroadsTUI)
        # Manually set up __init__ state without calling super().__init__()
        import threading
        from collections import deque
        app._engine = None
        app._switcher = None
        app._algo = "fixed_cycle"
        app._running = threading.Event()
        app._lock = threading.Lock()
        app._kpi_history = deque(maxlen=200)
        return app

    def test_init_state(self, tui):
        assert tui._engine is None
        assert tui._algo == "fixed_cycle"
        assert not tui._running.is_set()

    def test_reset_engine_creates_engine(self, tui):
        tui._reset_engine()
        assert tui._engine is not None
        assert tui._switcher is not None

    def test_action_start_sets_running(self, tui):
        tui._reset_engine()
        tui.action_start()
        assert tui._running.is_set()

    def test_action_stop_clears_running(self, tui):
        tui._reset_engine()
        tui.action_start()
        tui.action_stop()
        assert not tui._running.is_set()

    def test_action_restart_resets(self, tui):
        tui._reset_engine()
        tui.action_start()
        tui._reset_engine()
        assert tui._engine is not None
        assert not tui._running.is_set()

    def test_action_algo_fixed(self, tui):
        tui._reset_engine()
        tui.action_algo_fixed()
        assert tui._algo == "fixed_cycle"

    def test_action_algo_adaptive(self, tui):
        tui._reset_engine()
        tui.action_algo_adaptive()
        assert tui._algo == "adaptive_cycle"

    def test_action_algo_null(self, tui):
        tui._reset_engine()
        tui.action_algo_null()
        assert tui._algo == "null_control"

    def test_tick_and_refresh_not_running(self, tui):
        """_tick_and_refresh should be a no-op when not running."""
        tui._reset_engine()
        tui._engine.start()
        tui._tick_and_refresh()  # _running not set — should not step
        assert tui._engine.tick == 0

    def test_tick_and_refresh_running(self, tui):
        """_tick_and_refresh steps the engine when running is set."""
        tui._reset_engine()
        tui._engine.start()
        tui._running.set()
        with mock.patch.object(tui, "_refresh_ui"):
            tui._tick_and_refresh()
        assert tui._engine.tick == 1

    def test_on_event_safety_override(self, tui):
        """_on_event safety handler should not raise (query_one is mocked)."""
        from sim.enums import EventType
        from sim.events import SimEvent
        evt = SimEvent(tick=1, event_type=EventType.SAFETY_OVERRIDE,
                       payload={"rule": "R1", "explanation": "test"})
        mock_log = mock.MagicMock()
        with mock.patch.object(tui, "query_one", return_value=mock_log):
            tui._on_event(evt)
            mock_log.write.assert_called_once()

    def test_on_event_non_safety(self, tui):
        """_on_event for non-safety events should do nothing."""
        from sim.enums import EventType
        from sim.events import SimEvent
        evt = SimEvent(tick=1, event_type=EventType.KPI_SAMPLE, payload={})
        # Should not raise and should not call query_one
        with mock.patch.object(tui, "query_one") as mock_qo:
            tui._on_event(evt)
            mock_qo.assert_not_called()

    def test_refresh_ui_no_engine(self, tui):
        """_refresh_ui should be a no-op when engine is None."""
        tui._refresh_ui()  # should not raise

    def test_compose_yields_widgets(self, tui):
        """compose() should be a generator function."""
        import inspect

        from showcase.tui import CrossroadsTUI
        assert inspect.isgeneratorfunction(CrossroadsTUI.compose)
