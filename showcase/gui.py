"""
PyQt full-featured GUI for the crossroads simulation.

Uses:
  - QPainter for animated intersection canvas
  - PyQtCharts for live KPI line charts
  - QTimers for tick loop
  - QThread for background simulation

Run with:
    python3 -m showcase.gui
"""
from __future__ import annotations

import os
import sys
import signal
import collections
from typing import Optional

_QT_API = os.getenv("CROSSROADS_QT_API", "").strip().lower()

if _QT_API == "pyqt5":
    try:
        from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QComboBox, QSpinBox, QGroupBox,
            QSplitter, QTextEdit, QSlider, QStatusBar, QFrame,
        )
        from PyQt5.QtCore import (
            Qt, QTimer, QThread, pyqtSignal, QRectF, QPointF,
        )
        from PyQt5.QtGui import (
            QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QLinearGradient,
            QRadialGradient,
        )
        from PyQt5.QtChart import (
            QChart, QChartView, QLineSeries, QValueAxis, QSplineSeries,
        )
    except ModuleNotFoundError:
        _QT_API = "pyqt6"  # fall back silently

if _QT_API in ("pyqt6", ""):
    try:
        from PyQt6.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QComboBox, QSpinBox, QGroupBox,
            QSplitter, QTextEdit, QSlider, QStatusBar, QFrame,
        )
        from PyQt6.QtCore import (
            Qt, QTimer, QThread, pyqtSignal, QRectF, QPointF,
        )
        from PyQt6.QtGui import (
            QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QLinearGradient,
            QRadialGradient,
        )
        from PyQt6.QtCharts import (
            QChart, QChartView, QLineSeries, QValueAxis, QSplineSeries,
        )
    except ModuleNotFoundError:
        from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QComboBox, QSpinBox, QGroupBox,
            QSplitter, QTextEdit, QSlider, QStatusBar, QFrame,
        )
        from PyQt5.QtCore import (
            Qt, QTimer, QThread, pyqtSignal, QRectF, QPointF,
        )
        from PyQt5.QtGui import (
            QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QLinearGradient,
            QRadialGradient,
        )
        from PyQt5.QtChart import (
            QChart, QChartView, QLineSeries, QValueAxis, QSplineSeries,
        )

import algorithms
from algorithms.switcher import AlgorithmSwitcher
from safety.checker import SafetyChecker
from sim.engine import SimConfig, SimEngine
from sim.enums import Direction, LightPhase, EventType
from sim.intersection import Intersection

algorithms.discover()

# Qt5/Qt6 compatibility aliases
_QT_PENSTYLE = getattr(Qt, "PenStyle", Qt)
_QT_ALIGN = getattr(Qt, "AlignmentFlag", Qt)
_QT_ORIENT = getattr(Qt, "Orientation", Qt)
_QPAINTER_HINT = getattr(QPainter, "RenderHint", QPainter)
_QFONT_WEIGHT = getattr(QFont, "Weight", QFont)

QT_DASH_LINE = _QT_PENSTYLE.DashLine
QT_NO_PEN = _QT_PENSTYLE.NoPen
QT_ALIGN_BOTTOM = _QT_ALIGN.AlignBottom
QT_ALIGN_LEFT = _QT_ALIGN.AlignLeft
QT_ALIGN_CENTER = _QT_ALIGN.AlignCenter
QT_HORIZONTAL = _QT_ORIENT.Horizontal
QT_ANTIALIASING = _QPAINTER_HINT.Antialiasing
QT_FONT_BOLD = _QFONT_WEIGHT.Bold

# ── Colours ───────────────────────────────────────────────────────────────────
_PHASE_COLOR = {
    LightPhase.GREEN: QColor("#00e676"),
    LightPhase.YELLOW: QColor("#ffee58"),
    LightPhase.RED: QColor("#ef5350"),
    LightPhase.AMBER_FLASH: QColor("#ff9800"),
}
_ROAD_COLOR = QColor("#37474f")
_PAVEMENT_COLOR = QColor("#607d8b")
_BG_COLOR = QColor("#1a2a35")
_LINE_COLOR = QColor("#eceff1")

# ── Car palette ───────────────────────────────────────────────────────────────
_CAR_COLORS = [
    QColor("#ef5350"), QColor("#42a5f5"), QColor("#66bb6a"),
    QColor("#ffca28"), QColor("#ab47bc"), QColor("#26c6da"),
    QColor("#ff7043"), QColor("#8d6e63"), QColor("#78909c"), QColor("#d4e157"),
]

# ── Layout constants ──────────────────────────────────────────────────────────
_ROAD_W = 96          # 2 lanes x 48 px
_LANE_W = _ROAD_W // 2
_ZEBRA_W = 14
_ZEBRA_STRIPES = 5

# ── Bezier / math helpers ─────────────────────────────────────────────────────
import math as _math
import random as _random


def _lerp2(t, p0, p1):
    return (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)


def _qbez(t, p0, p1, p2):
    mt = 1.0 - t
    return (mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
            mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1])


def _qbez_angle(t, p0, p1, p2):
    mt = 1.0 - t
    dx = 2 * mt * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0])
    dy = 2 * mt * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1])
    return _math.degrees(_math.atan2(dy, dx)) if (dx or dy) else 0.0


def _cbez(t, p0, p1, p2, p3):
    mt = 1.0 - t
    return (mt**3 * p0[0] + 3*mt**2*t * p1[0] + 3*mt*t**2 * p2[0] + t**3 * p3[0],
            mt**3 * p0[1] + 3*mt**2*t * p1[1] + 3*mt*t**2 * p2[1] + t**3 * p3[1])


def _cbez_angle(t, p0, p1, p2, p3):
    mt = 1.0 - t
    dx = 3*(mt**2*(p1[0]-p0[0]) + 2*mt*t*(p2[0]-p1[0]) + t**2*(p3[0]-p2[0]))
    dy = 3*(mt**2*(p1[1]-p0[1]) + 2*mt*t*(p2[1]-p1[1]) + t**2*(p3[1]-p2[1]))
    return _math.degrees(_math.atan2(dy, dx)) if (dx or dy) else 0.0


# Entry angles: direction the car faces when approaching the junction.
# Convention: 0=east, 90=south, 180=west, 270=north (screen coords, y down).
_ENTRY_ANGLE = {
    Direction.NORTH: 90.0,    # coming FROM north, travelling south  (down)
    Direction.SOUTH: 270.0,   # coming FROM south, travelling north  (up)
    Direction.EAST:  180.0,   # coming FROM east,  travelling west   (left)
    Direction.WEST:  0.0,     # coming FROM west,  travelling east   (right)
}

# Right-hand traffic lane centres (offset from road centre cx/cy):
#   inbound NORTH  lane:  x = cx - hl   (southbound, left of centre when facing south)
#   inbound SOUTH  lane:  x = cx + hl   (northbound, right of centre when facing north)
#   inbound EAST   lane:  y = cy + hl   (westbound,  lower half)
#   inbound WEST   lane:  y = cy - hl   (eastbound,  upper half)


def _vehicle_pos_angle(entry: "Direction", turn: str, progress: float,
                       cx: int, cy: int, hrw: int, lw: int, W: int, H: int):
    """
    Returns (x, y, angle_deg) for a vehicle along its complete road journey.
      progress 0.0 = head of approach arm,  1.0 = exited on the far side.
    Phases:  approach 0->0.35 | junction 0.35->0.65 | exit 0.65->1.0
    """
    hl = lw // 2

    if entry == Direction.NORTH:
        arm_start = (cx - hl, 0)
        p_in      = (cx - hl, cy - hrw)
        if turn == 'straight':
            p_out, arm_end, exit_a = (cx - hl, cy + hrw), (cx - hl, H),     90.0
        elif turn == 'right':   # -> WEST
            p_out, arm_end, exit_a = (cx - hrw, cy + hl), (0,       cy + hl), 180.0
        else:                   # left -> EAST
            p_out, arm_end, exit_a = (cx + hrw, cy - hl), (W,       cy - hl),   0.0

    elif entry == Direction.SOUTH:
        arm_start = (cx + hl, H)
        p_in      = (cx + hl, cy + hrw)
        if turn == 'straight':
            p_out, arm_end, exit_a = (cx + hl, cy - hrw), (cx + hl, 0),    270.0
        elif turn == 'right':   # -> EAST
            p_out, arm_end, exit_a = (cx + hrw, cy - hl), (W,       cy - hl),   0.0
        else:                   # left -> WEST
            p_out, arm_end, exit_a = (cx - hrw, cy + hl), (0,       cy + hl), 180.0

    elif entry == Direction.EAST:
        arm_start = (W, cy + hl)
        p_in      = (cx + hrw, cy + hl)
        if turn == 'straight':
            p_out, arm_end, exit_a = (cx - hrw, cy + hl), (0,       cy + hl), 180.0
        elif turn == 'right':   # -> NORTH
            p_out, arm_end, exit_a = (cx + hl, cy - hrw), (cx + hl, 0),    270.0
        else:                   # left -> SOUTH
            p_out, arm_end, exit_a = (cx - hl, cy + hrw), (cx - hl, H),     90.0

    else:  # WEST
        arm_start = (0, cy - hl)
        p_in      = (cx - hrw, cy - hl)
        if turn == 'straight':
            p_out, arm_end, exit_a = (cx + hrw, cy - hl), (W,       cy - hl),   0.0
        elif turn == 'right':   # -> SOUTH
            p_out, arm_end, exit_a = (cx - hl, cy + hrw), (cx - hl, H),     90.0
        else:                   # left -> NORTH
            p_out, arm_end, exit_a = (cx + hl, cy - hrw), (cx + hl, 0),    270.0

    entry_a = _ENTRY_ANGLE[entry]

    # ── Phase 1: approach ────────────────────────────────────────────────────
    if progress < 0.35:
        t = progress / 0.35
        x, y = _lerp2(t, arm_start, p_in)
        return x, y, entry_a

    # ── Phase 2: junction ────────────────────────────────────────────────────
    if progress < 0.65:
        t = (progress - 0.35) / 0.30
        if turn == 'straight':
            x, y = _lerp2(t, p_in, p_out)
            return x, y, entry_a
        elif turn == 'right':
            # Quadratic bezier; corner CP = (entry_x, exit_y) or (exit_x, entry_y)
            if entry in (Direction.NORTH, Direction.SOUTH):
                cp = (p_in[0], p_out[1])
            else:
                cp = (p_out[0], p_in[1])
            x, y = _qbez(t, p_in, cp, p_out)
            return x, y, _qbez_angle(t, p_in, cp, p_out)
        else:
            # Cubic bezier arcing around the junction centre
            if entry in (Direction.NORTH, Direction.SOUTH):
                p1 = (p_in[0], cy)
                p2 = (cx, p_out[1])
            else:
                p1 = (cx, p_in[1])
                p2 = (p_out[0], cy)
            x, y = _cbez(t, p_in, p1, p2, p_out)
            return x, y, _cbez_angle(t, p_in, p1, p2, p_out)

    # ── Phase 3: exit ────────────────────────────────────────────────────────
    t = (progress - 0.65) / 0.35
    x, y = _lerp2(t, p_out, arm_end)
    return x, y, exit_a


# ── Animated vehicle ──────────────────────────────────────────────────────────

class _AnimVehicle:
    __slots__ = ('entry', 'turn', 'progress', 'color', 'speed')

    def __init__(self, entry: "Direction", turn: str, color: "QColor"):
        self.entry = entry
        self.turn  = turn
        self.color = color
        self.progress = 0.0
        self.speed = {'straight': 0.025, 'right': 0.033, 'left': 0.018}[turn]

    def advance(self) -> bool:
        """Advance one tick. Returns True while still active."""
        self.progress = min(1.0, self.progress + self.speed)
        return self.progress < 1.0


# ── Car shape painter ─────────────────────────────────────────────────────────

def _draw_car(p: "QPainter", cx: float, cy: float, angle_deg: float,
              body_color: "QColor", car_w: int = 22, car_h: int = 13) -> None:
    """Top-down car centred at (cx,cy), rotated angle_deg (0=east, 90=south)."""
    p.save()
    p.translate(cx, cy)
    p.rotate(angle_deg)
    hw, hh = car_w // 2, car_h // 2

    p.setPen(QT_NO_PEN)
    p.setBrush(QBrush(QColor(0, 0, 0, 80)))
    p.drawRoundedRect(-hw + 2, -hh + 2, car_w, car_h, 3, 3)

    p.setBrush(QBrush(body_color))
    p.setPen(QPen(body_color.darker(150), 1))
    p.drawRoundedRect(-hw, -hh, car_w, car_h, 3, 3)

    p.setPen(QT_NO_PEN)
    p.setBrush(QBrush(QColor(170, 220, 255, 210)))
    p.drawRoundedRect(hw - 8, -hh + 2, 6, car_h - 4, 1, 1)
    p.drawRoundedRect(-hw + 2, -hh + 2, 5, car_h - 4, 1, 1)

    roof = body_color.lighter(150)
    roof.setAlpha(150)
    p.setBrush(QBrush(roof))
    p.drawRoundedRect(-hw + 7, -hh + 2, car_w - 15, car_h - 4, 2, 2)

    for wx, wy in [(-hw + 2, -hh - 1), (-hw + 2, hh - 2),
                   (hw - 8,  -hh - 1), (hw - 8,  hh - 2)]:
        p.setBrush(QBrush(QColor("#424242")))
        p.drawEllipse(wx, wy, 6, 3)
        p.setBrush(QBrush(QColor("#212121")))
        p.drawEllipse(wx + 1, wy, 4, 3)

    p.setBrush(QBrush(QColor("#fff9c4")))
    p.drawEllipse(hw - 2, -hh + 1, 3, 3)
    p.drawEllipse(hw - 2,  hh - 4, 3, 3)

    p.setBrush(QBrush(QColor("#e53935")))
    p.drawEllipse(-hw - 1, -hh + 1, 3, 3)
    p.drawEllipse(-hw - 1,  hh - 4, 3, 3)

    p.restore()


# ── Intersection Canvas ───────────────────────────────────────────────────────

class IntersectionCanvas(QWidget):
    """
    Animated 4-way intersection (right-hand traffic).
      - Two lanes per arm
      - Zebra crossings on all four sides
      - Full-journey vehicle animation: approach -> junction -> exit arm
      - Three turn types with smooth bezier paths
      - Smart signal panels showing permitted movements per phase
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(540, 540)
        self._lights: dict   = {d: LightPhase.RED for d in Direction}
        self._queues: dict   = {d: 0 for d in Direction}
        self._crossing: list = []
        self._vehicles: list = []
        self._car_counter    = 0
        self._flash_state    = True
        self._anim_timer     = QTimer(self)
        self._anim_timer.timeout.connect(self._on_tick)
        # Timer only runs while widget is visible (avoids blocking tests)

    def showEvent(self, event):
        super().showEvent(event)
        self._anim_timer.start(80)   # ~12 fps

    def hideEvent(self, event):
        super().hideEvent(event)
        self._anim_timer.stop()

    # Backward-compat aliases used by tests
    def _on_flash(self):
        self._on_tick()

    def _toggle_flash(self):
        self._flash_state = not self._flash_state

    def _on_tick(self):
        self._flash_state = not self._flash_state
        self._advance_vehicles()
        self.update()

    def _advance_vehicles(self):
        """Move vehicles forward; spawn new ones from green queues."""
        self._vehicles = [v for v in self._vehicles if v.advance()]
        for d in Direction:
            phase = self._lights.get(d)
            if phase not in (LightPhase.GREEN, LightPhase.YELLOW):
                continue
            if self._queues.get(d, 0) == 0:
                continue
            # Throttle: don't spawn if a very-new vehicle already occupies the arm
            if any(v.entry == d and v.progress < 0.12 for v in self._vehicles):
                continue
            r = _random.random()
            turn  = 'straight' if r < 0.55 else ('right' if r < 0.85 else 'left')
            color = _CAR_COLORS[self._car_counter % len(_CAR_COLORS)]
            self._car_counter += 1
            self._vehicles.append(_AnimVehicle(d, turn, color))

    def update_state(self, lights: dict, queues: dict, crossing: list):
        self._lights   = {Direction(k): LightPhase(v["phase"])
                          for k, v in lights.items()}
        self._queues   = {Direction(k): v for k, v in queues.items()}
        self._crossing = crossing

    # ── Main paint ────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QT_ANTIALIASING)
        W, H = self.width(), self.height()
        cx, cy = W // 2, H // 2
        hrw = _ROAD_W // 2
        zw  = _ZEBRA_W

        # Grass
        p.fillRect(0, 0, W, H, QColor("#2d4a2d"))
        # Pavement corners
        for qx, qy in [(0, 0), (cx + hrw, 0), (0, cy + hrw), (cx + hrw, cy + hrw)]:
            p.fillRect(int(qx), int(qy), cx - hrw, cy - hrw, QColor("#546e7a"))
        # Tarmac roads
        p.fillRect(cx - hrw, 0,        _ROAD_W, H,       QColor("#37474f"))
        p.fillRect(0,        cy - hrw, W,       _ROAD_W, QColor("#37474f"))
        # Zebra crossings
        for d in Direction:
            self._draw_zebra(p, cx, cy, hrw, zw, d)
        # Junction box
        p.fillRect(cx - hrw, cy - hrw, _ROAD_W, _ROAD_W, QColor("#455a64"))
        # Lane markings
        self._draw_lane_markings(p, cx, cy, hrw, W, H)
        # Kerb lines
        p.setPen(QPen(QColor("#90a4ae"), 2))
        for x0, y0, x1, y1 in [
            (cx-hrw, 0,        cx-hrw, cy-hrw), (cx-hrw, cy+hrw, cx-hrw, H),
            (cx+hrw, 0,        cx+hrw, cy-hrw), (cx+hrw, cy+hrw, cx+hrw, H),
            (0,      cy-hrw,   cx-hrw, cy-hrw), (cx+hrw, cy-hrw, W,      cy-hrw),
            (0,      cy+hrw,   cx-hrw, cy+hrw), (cx+hrw, cy+hrw, W,      cy+hrw),
        ]:
            p.drawLine(int(x0), int(y0), int(x1), int(y1))
        # Static queue cars (facing toward junction)
        for d in Direction:
            self._draw_queue_cars(p, d, cx, cy, hrw)
        # Full-journey animated vehicles
        for v in self._vehicles:
            x, y, ang = _vehicle_pos_angle(
                v.entry, v.turn, v.progress, cx, cy, hrw, _LANE_W, W, H)
            _draw_car(p, x, y, ang, v.color)
        # Traffic signals
        for d in Direction:
            self._draw_signal(p, d, cx, cy, hrw)
        # Direction labels
        p.setPen(QPen(QColor("#eceff1"), 1))
        p.setFont(QFont("Monospace", 9, QT_FONT_BOLD))
        for d, (lx, ly) in {
            Direction.NORTH: (cx,      16),
            Direction.SOUTH: (cx,      H - 6),
            Direction.EAST:  (W - 12,  cy + 4),
            Direction.WEST:  (14,      cy + 4),
        }.items():
            p.drawText(int(lx) - 5, int(ly), d.value.upper())
        p.end()

    # ── Zebra crossing ────────────────────────────────────────────────────────

    def _draw_zebra(self, p, cx, cy, hrw, zw, d: Direction):
        n      = _ZEBRA_STRIPES
        stripe = _ROAD_W / (n * 2)
        p.setPen(QT_NO_PEN)
        p.setBrush(QBrush(QColor(240, 240, 240, 230)))
        if d == Direction.NORTH:
            for i in range(n):
                p.drawRect(int(cx - hrw + i * stripe * 2), cy - hrw - zw,
                           int(stripe), zw)
        elif d == Direction.SOUTH:
            for i in range(n):
                p.drawRect(int(cx - hrw + i * stripe * 2), cy + hrw,
                           int(stripe), zw)
        elif d == Direction.EAST:
            for i in range(n):
                p.drawRect(cx + hrw, int(cy - hrw + i * stripe * 2),
                           zw, int(stripe))
        else:
            for i in range(n):
                p.drawRect(cx - hrw - zw, int(cy - hrw + i * stripe * 2),
                           zw, int(stripe))

    # ── Lane markings ─────────────────────────────────────────────────────────

    def _draw_lane_markings(self, p, cx, cy, hrw, W, H):
        zw = _ZEBRA_W
        p.setPen(QPen(QColor("#ffffff"), 1, QT_DASH_LINE))
        p.drawLine(cx, 0,        cx,      cy - hrw)
        p.drawLine(cx, cy + hrw, cx,      H)
        p.drawLine(0,  cy,       cx - hrw, cy)
        p.drawLine(cx + hrw, cy, W,        cy)
        p.setPen(QPen(QColor("#ffffff"), 3))
        p.drawLine(cx - hrw, cy - hrw - zw, cx + hrw, cy - hrw - zw)
        p.drawLine(cx - hrw, cy + hrw + zw, cx + hrw, cy + hrw + zw)
        p.drawLine(cx - hrw - zw, cy - hrw, cx - hrw - zw, cy + hrw)
        p.drawLine(cx + hrw + zw, cy - hrw, cx + hrw + zw, cy + hrw)

    # ── Static queue cars (face TOWARD junction) ──────────────────────────────

    def _draw_queue_cars(self, p, d: Direction, cx, cy, hrw):
        q = self._queues.get(d, 0)
        if not q:
            return
        hl  = _LANE_W // 2
        gap = 30
        for i in range(min(q, 8)):
            color = _CAR_COLORS[(hash(d.value) + i) % len(_CAR_COLORS)]
            off   = hrw + _ZEBRA_W + 8 + i * gap
            if d == Direction.NORTH:
                _draw_car(p, cx - hl, cy - off, 90,  color)  # faces south ↓
            elif d == Direction.SOUTH:
                _draw_car(p, cx + hl, cy + off, 270, color)  # faces north ↑
            elif d == Direction.EAST:
                _draw_car(p, cx + off, cy + hl, 180, color)  # faces west ←
            else:
                _draw_car(p, cx - off, cy - hl, 0,   color)  # faces east →

    # ── Traffic signal with smart turn-arrow panel ────────────────────────────

    def _draw_signal(self, p, d: Direction, cx, cy, hrw):
        phase = self._lights[d]
        zw    = _ZEBRA_W
        if d == Direction.NORTH:
            px, py = cx + hrw + 5,      cy - hrw - zw - 2
        elif d == Direction.SOUTH:
            px, py = cx - hrw - 5,      cy + hrw + zw + 2
        elif d == Direction.EAST:
            px, py = cx + hrw + zw + 2, cy + hrw + 5
        else:
            px, py = cx - hrw - zw - 2, cy - hrw - 5

        # Pole
        p.setPen(QPen(QColor("#616161"), 3))
        p.drawLine(int(px), int(py), int(px), int(py) - 32)

        # Housing
        bw, bh = 16, 44
        bx, by = int(px) - bw // 2, int(py) - 32 - bh
        p.setBrush(QBrush(QColor("#1a1a1a")))
        p.setPen(QPen(QColor("#424242"), 1))
        p.drawRoundedRect(bx, by, bw, bh, 2, 2)

        # Lamps
        amber_on = self._flash_state
        for lamp_color, lamp_y, is_on in [
            (QColor("#c62828"), by +  3, phase == LightPhase.RED),
            (QColor("#f9a825"), by + 17, phase == LightPhase.YELLOW or
             (phase == LightPhase.AMBER_FLASH and amber_on)),
            (QColor("#2e7d32"), by + 31, phase == LightPhase.GREEN),
        ]:
            c = lamp_color if is_on else QColor(
                lamp_color.red() // 5, lamp_color.green() // 5, lamp_color.blue() // 5)
            grad = QRadialGradient(px, lamp_y + 5, 6)
            grad.setColorAt(0.0, c.lighter(160))
            grad.setColorAt(1.0, c)
            p.setBrush(QBrush(grad))
            p.setPen(QT_NO_PEN)
            p.drawEllipse(int(px) - 5, lamp_y, 10, 10)




# ── Live chart ────────────────────────────────────────────────────────────────

class LiveChart(QChartView):
    """Scrolling line chart for KPI data."""

    def __init__(self, title: str, y_label: str, color: QColor, parent=None):
        super().__init__(parent)
        self._series = QSplineSeries()
        self._series.setColor(color)
        self._series.setPen(QPen(color, 2))

        self._chart = QChart()
        self._chart.addSeries(self._series)
        self._chart.setTitle(title)
        self._chart.setBackgroundBrush(QBrush(QColor("#1e2d3a")))
        self._chart.setTitleBrush(QBrush(QColor("#eceff1")))
        self._chart.legend().hide()

        self._x_axis = QValueAxis()
        self._x_axis.setLabelFormat("%d")
        self._x_axis.setTitleText("Tick")
        self._x_axis.setLabelsColor(QColor("#b0bec5"))
        self._x_axis.setGridLineColor(QColor("#37474f"))
        self._x_axis.setRange(0, 200)

        self._y_axis = QValueAxis()
        self._y_axis.setLabelFormat("%.1f")
        self._y_axis.setTitleText(y_label)
        self._y_axis.setLabelsColor(QColor("#b0bec5"))
        self._y_axis.setGridLineColor(QColor("#37474f"))
        self._y_axis.setRange(0, 10)

        self._chart.addAxis(self._x_axis, QT_ALIGN_BOTTOM)
        self._chart.addAxis(self._y_axis, QT_ALIGN_LEFT)
        self._series.attachAxis(self._x_axis)
        self._series.attachAxis(self._y_axis)

        self.setChart(self._chart)
        self.setRenderHint(QT_ANTIALIASING)
        self.setMinimumHeight(160)

        self._points: list[tuple[float, float]] = []
        self._window = 200

    def add_point(self, x: float, y: float) -> None:
        self._points.append((x, y))
        if len(self._points) > self._window:
            self._points = self._points[-self._window:]

        self._series.clear()
        for px, py in self._points:
            self._series.append(px, py)

        if self._points:
            xs = [pt[0] for pt in self._points]
            ys = [pt[1] for pt in self._points]
            self._x_axis.setRange(min(xs), max(xs) + 1)
            max_y = max(ys) * 1.2 if max(ys) > 0 else 10
            self._y_axis.setRange(0, max_y)

    def reset(self) -> None:
        self._points.clear()
        self._series.clear()


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Main application window."""

    _state_updated = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Crossroads Simulator — PyQt6 Showcase")
        self.setMinimumSize(1100, 700)
        self._engine: Optional[SimEngine] = None
        self._switcher: Optional[AlgorithmSwitcher] = None
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._do_tick)
        self._state_updated.connect(self._apply_state)
        self._setup_ui()
        self._new_engine()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(8)

        # ── Left: intersection + controls ─────────────────────────────────
        left = QVBoxLayout()

        self._canvas = IntersectionCanvas()
        left.addWidget(self._canvas)

        ctrl_box = QGroupBox("Controls")
        ctrl_layout = QHBoxLayout(ctrl_box)

        self._btn_start = QPushButton("▶ Start")
        self._btn_start.setStyleSheet("background:#2e7d32; color:white; font-weight:bold;")
        self._btn_start.clicked.connect(self._start)

        self._btn_stop = QPushButton("⏸ Pause")
        self._btn_stop.setStyleSheet("background:#bf360c; color:white; font-weight:bold;")
        self._btn_stop.clicked.connect(self._stop)

        self._btn_reset = QPushButton("↺ Reset")
        self._btn_reset.clicked.connect(self._reset)

        self._algo_combo = QComboBox()
        self._algo_combo.addItems(sorted(algorithms.available()))
        self._algo_combo.currentTextChanged.connect(self._switch_algo)

        self._speed_slider = QSlider(QT_HORIZONTAL)
        self._speed_slider.setRange(50, 1000)
        self._speed_slider.setValue(200)
        self._speed_slider.valueChanged.connect(self._update_speed)
        self._speed_slider.setToolTip("Tick speed (ms)")

        ctrl_layout.addWidget(self._btn_start)
        ctrl_layout.addWidget(self._btn_stop)
        ctrl_layout.addWidget(self._btn_reset)
        ctrl_layout.addWidget(QLabel("Algorithm:"))
        ctrl_layout.addWidget(self._algo_combo)
        ctrl_layout.addWidget(QLabel("Speed:"))
        ctrl_layout.addWidget(self._speed_slider)

        left.addWidget(ctrl_box)

        # ── KPI labels ─────────────────────────────────────────────────────
        kpi_box = QGroupBox("Live KPIs")
        kpi_layout = QHBoxLayout(kpi_box)
        self._lbl_tick = self._kpi_label("Tick", "0")
        self._lbl_passed = self._kpi_label("Passed", "0")
        self._lbl_wait = self._kpi_label("Avg Wait", "0.0")
        self._lbl_thr = self._kpi_label("Throughput", "0.0")
        self._lbl_null = self._kpi_label("Null%", "0.0")
        for w in [self._lbl_tick, self._lbl_passed, self._lbl_wait,
                  self._lbl_thr, self._lbl_null]:
            kpi_layout.addWidget(w)

        left.addWidget(kpi_box)

        # ── Right: charts + safety log ─────────────────────────────────────
        right = QVBoxLayout()

        self._chart_wait = LiveChart("Avg Wait (ticks)", "ticks", QColor("#42a5f5"))
        self._chart_thr = LiveChart("Throughput / 100 ticks", "/100t", QColor("#66bb6a"))
        self._chart_null = LiveChart("Null Control %", "%", QColor("#ef9a9a"))

        right.addWidget(self._chart_wait)
        right.addWidget(self._chart_thr)
        right.addWidget(self._chart_null)

        # Safety log
        log_box = QGroupBox("Safety Log")
        log_layout = QVBoxLayout(log_box)
        self._safety_log = QTextEdit()
        self._safety_log.setReadOnly(True)
        self._safety_log.setMaximumHeight(120)
        self._safety_log.setStyleSheet(
            "background:#1a0000; color:#ff8a80; font-family:monospace; font-size:10px;"
        )
        log_layout.addWidget(self._safety_log)
        right.addWidget(log_box)

        # Assemble
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMaximumWidth(480)

        right_widget = QWidget()
        right_widget.setLayout(right)

        root.addWidget(left_widget)
        root.addWidget(right_widget)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready — press ▶ Start")

        # Style sheet
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #1a2a35; color: #eceff1; }
            QGroupBox { border: 1px solid #37474f; border-radius: 4px;
                        margin-top: 8px; padding: 4px; color: #90caf9; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; }
            QPushButton { border: 1px solid #546e7a; border-radius: 4px;
                          padding: 4px 10px; background: #263238; }
            QPushButton:hover { background: #37474f; }
            QComboBox { background: #263238; border: 1px solid #546e7a;
                        border-radius: 4px; padding: 2px 4px; }
            QComboBox QAbstractItemView { background: #263238; }
            QSlider::groove:horizontal { height: 4px; background: #546e7a; border-radius: 2px; }
            QSlider::handle:horizontal { width: 14px; height: 14px; background: #42a5f5;
                                          border-radius: 7px; margin: -5px 0; }
        """)

    def _kpi_label(self, title: str, value: str) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        lbl = QLabel(value)
        lbl.setFont(QFont("Monospace", 14, QT_FONT_BOLD))
        lbl.setAlignment(QT_ALIGN_CENTER)
        lbl.setStyleSheet("color: #00e5ff;")
        layout.addWidget(lbl)
        box._value_label = lbl  # type: ignore[attr-defined]
        return box

    def _new_engine(self):
        algo = self._algo_combo.currentText() if hasattr(self, "_algo_combo") else "fixed_cycle"
        cfg = SimConfig(seed=42, algorithm=algo, tick_step_ms=200, max_ticks=None)
        ix = Intersection()
        self._switcher = AlgorithmSwitcher(algo)
        self._engine = SimEngine(cfg, ix, self._switcher, SafetyChecker())
        self._engine.add_listener(self._on_sim_event)

    def _on_sim_event(self, event) -> None:
        if event.event_type == EventType.SAFETY_OVERRIDE:
            rule = event.payload.get("rule", "?")
            expl = event.payload.get("explanation", "")[:100]
            self._safety_log.append(f"[T{event.tick}] {rule}: {expl}")

    def _do_tick(self):
        if not self._engine:
            return
        kpi = self._engine.step()
        if kpi:
            snap = self._engine.snapshot_state()
            snap["_kpi"] = {
                "tick": kpi.tick,
                "passed": kpi.vehicles_passed,
                "avg_wait": kpi.avg_wait_ticks,
                "throughput": kpi.throughput_per_100_ticks,
                "null_pct": kpi.pct_null_control,
            }
            self._state_updated.emit(snap)
        else:
            snap = self._engine.snapshot_state()
            self._state_updated.emit(snap)

    def _apply_state(self, snap: dict):
        self._canvas.update_state(snap["lights"], snap["queues"], snap.get("crossing", []))

        # Tick counter in status bar
        self._status.showMessage(
            f"Tick {snap['tick']} | Algorithm: {snap.get('algorithm', '?')} | "
            f"Vehicles: {len(snap.get('vehicles', []))}"
        )

        # KPI labels
        self._lbl_tick._value_label.setText(str(snap["tick"]))  # type: ignore
        if "_kpi" in snap:
            k = snap["_kpi"]
            self._lbl_passed._value_label.setText(str(k["passed"]))  # type: ignore
            self._lbl_wait._value_label.setText(f"{k['avg_wait']:.1f}")  # type: ignore
            self._lbl_thr._value_label.setText(f"{k['throughput']:.1f}")  # type: ignore
            self._lbl_null._value_label.setText(f"{k['null_pct']:.1f}%")  # type: ignore
            t = k["tick"]
            self._chart_wait.add_point(t, k["avg_wait"])
            self._chart_thr.add_point(t, k["throughput"])
            self._chart_null.add_point(t, k["null_pct"])

    def _start(self):
        if self._engine and not self._engine.running:
            self._engine.start()
        speed = self._speed_slider.value()
        self._tick_timer.start(speed)
        self._status.showMessage("Running…")

    def _stop(self):
        self._tick_timer.stop()
        self._status.showMessage("Paused")

    def _reset(self):
        self._tick_timer.stop()
        self._new_engine()
        self._canvas.update_state(
            {d.value: {"phase": "red"} for d in Direction},
            {d.value: 0 for d in Direction},
            [],
        )
        for chart in [self._chart_wait, self._chart_thr, self._chart_null]:
            chart.reset()
        self._safety_log.clear()
        self._status.showMessage("Reset — press ▶ Start")

    def _switch_algo(self, name: str):
        if self._switcher and name in algorithms.available():
            self._switcher.request_switch(name)

    def _update_speed(self, val: int):
        if self._tick_timer.isActive():
            self._tick_timer.setInterval(val)


def main():
    # Let Ctrl+C terminate the app cleanly instead of showing a callback traceback.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    app.setApplicationName("Crossroads Simulator")
    window = MainWindow()
    window.show()
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        # Return silently when interrupted from terminal (e.g. offscreen runs).
        raise SystemExit(130)


if __name__ == "__main__":
    main()
