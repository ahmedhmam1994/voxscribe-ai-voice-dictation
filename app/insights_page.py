"""The Insights page: totals, speed, streak, this week, a 12-week activity
grid and a few highlights, all worked out locally from core/history.py.

The charts are painted by hand (no charting dependency to bundle). When the
page opens, numbers count up, the week's bars grow and the activity grid
fills in from left to right; with Windows animations off everything simply
appears.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from app.motion import animations_enabled, count_up
from core import history

ACCENT = QColor("#3ecf8e")
TEXT = QColor("#eceef4")
MUTED = QColor("#8b8d9c")
FAINT = QColor("#5c5e6c")
EMPTY_CELL = QColor("#2a2d3a")
IDLE_BAR = QColor("#2e3140")

_DAY_INITIALS = ["M", "T", "W", "T", "F", "S", "S"]
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

PAGE_STYLESHEET = """
QWidget#insightsCard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1f212c, stop:1 #1a1c26);
    border: 1px solid #242631;
    border-radius: 14px;
}
QLabel#insightsCaption {
    color: #8b8d9c; font-size: 11px; font-weight: 700; letter-spacing: 0.6px;
}
QLabel#insightsBig {
    color: #3ecf8e; font-size: 44px; font-weight: 800;
}
QLabel#insightsValue {
    color: #eceef4; font-size: 26px; font-weight: 700;
}
QLabel#insightsUnit {
    color: #8b8d9c; font-size: 13px; font-weight: 600;
}
QLabel#insightsSub {
    color: #8b8d9c; font-size: 12px;
}
QLabel#insightsSubStrong {
    color: #eceef4; font-size: 13px; font-weight: 600;
}
QScrollBar:vertical {
    background: transparent; width: 10px; margin: 4px 2px 4px 0;
}
QScrollBar::handle:vertical {
    background: #2b2e3b; border-radius: 4px; min-height: 40px;
}
QScrollBar::handle:vertical:hover { background: #3a3d4c; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QLabel#insightsHighlightValue {
    color: #eceef4; font-size: 15px; font-weight: 700;
}
"""


def _card() -> tuple[QWidget, QVBoxLayout]:
    card = QWidget()
    card.setObjectName("insightsCard")
    card.setAttribute(Qt.WA_StyledBackground, True)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 16, 20, 16)
    layout.setSpacing(6)
    return card, layout


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    return label


class _HeroGlow(QWidget):
    """The top card: a soft green glow behind the total, so the page has one
    clear focal point instead of a row of equal boxes."""

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        base = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base.setColorAt(0.0, QColor("#1c2a25"))
        base.setColorAt(0.55, QColor("#1b1e28"))
        base.setColorAt(1.0, QColor("#1a1c26"))
        painter.setPen(QPen(QColor(62, 207, 142, 60), 1))
        painter.setBrush(base)
        painter.drawRoundedRect(rect, 16, 16)
        center = QPointF(rect.width() * 0.12, rect.height() * 0.1)
        glow = QRadialGradient(center, rect.width() * 0.5)
        glow.setColorAt(0.0, QColor(62, 207, 142, 46))
        glow.setColorAt(1.0, QColor(62, 207, 142, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawRoundedRect(rect, 16, 16)


class _SpeedBars(QWidget):
    """Your speaking speed next to a typical typing speed."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(34)
        self.wpm = 0
        self.progress = 1.0

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        top = max(self.wpm, history.TYPING_WPM, 1)
        label_w = 46
        track = self.width() - label_w
        for row, (name, value, color) in enumerate(
            (("You", self.wpm, ACCENT), ("Typing", history.TYPING_WPM, IDLE_BAR))
        ):
            y = row * 18
            painter.setPen(MUTED)
            painter.drawText(QRectF(0, y, label_w, 14), Qt.AlignVCenter | Qt.AlignLeft, name)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#23252f"))
            painter.drawRoundedRect(QRectF(label_w, y + 4, track, 6), 3, 3)
            width = track * value / top * (self.progress if row == 0 else 1.0)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(label_w, y + 4, max(6.0, width), 6), 3, 3)


class _WeekDots(QWidget):
    """Seven dots for the last seven days, filled on days with a dictation."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(34)
        self.active = [False] * 7
        self.today = date.today()

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(QFont("Segoe UI", 7, QFont.DemiBold))
        step = min(28.0, self.width() / 7)
        for i, on in enumerate(self.active):
            cx = step * i + step / 2
            day = self.today - timedelta(days=6 - i)
            if on:
                painter.setPen(Qt.NoPen)
                painter.setBrush(ACCENT)
            else:
                painter.setPen(QPen(QColor("#3a3d4c"), 1.4))
                painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, 8), 6, 6)
            painter.setPen(TEXT if i == 6 else FAINT)
            painter.drawText(
                QRectF(cx - 8, 18, 16, 14), Qt.AlignCenter, _DAY_INITIALS[day.weekday()]
            )


class _WeekChart(QWidget):
    """Words per day this week as bars, today in green with its count on top."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(150)
        self.values = [0] * 7
        self.today = date.today()
        self.progress = 1.0

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bottom = h - 24
        top_room = 22
        peak = max(max(self.values), 1)
        slot = w / 7
        bar_w = min(34.0, slot * 0.46)
        for i, value in enumerate(self.values):
            # Bars grow one after another, left to right.
            local = min(1.0, max(0.0, self.progress * 1.6 - i * 0.09))
            eased = 1 - (1 - local) ** 3
            full = (bottom - top_room) * value / peak
            bar_h = max(5.0, full * eased)
            x = slot * i + (slot - bar_w) / 2
            is_today = i == 6
            painter.setPen(Qt.NoPen)
            if is_today:
                grad = QLinearGradient(QPointF(0, bottom - bar_h), QPointF(0, bottom))
                grad.setColorAt(0.0, QColor("#5ce3a6"))
                grad.setColorAt(1.0, QColor("#2fae76"))
                painter.setBrush(grad)
            else:
                painter.setBrush(IDLE_BAR if value else QColor("#262833"))
            painter.drawRoundedRect(QRectF(x, bottom - bar_h, bar_w, bar_h), 6, 6)
            if value and (is_today or value == peak) and local >= 1.0:
                painter.setPen(TEXT if is_today else MUTED)
                painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                painter.drawText(
                    QRectF(x - 20, bottom - bar_h - 18, bar_w + 40, 16),
                    Qt.AlignCenter,
                    f"{value:,}",
                )
            day = self.today - timedelta(days=6 - i)
            painter.setPen(TEXT if is_today else FAINT)
            painter.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
            painter.drawText(
                QRectF(slot * i, bottom + 6, slot, 16), Qt.AlignCenter, _DAY_INITIALS[day.weekday()]
            )


class _ActivityGrid(QWidget):
    """Twelve weeks of days as small squares, darker green on busier days.
    Hovering a square shows its date and word count."""

    CELL = 20
    GAP = 4
    LEFT = 30
    TOP = 18

    def __init__(self) -> None:
        super().__init__()
        self.setMouseTracking(True)
        self.start = date.today()
        self.values: list[int] = []
        self.progress = 1.0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(self.TOP + 7 * (self.CELL + self.GAP) + 4)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.LEFT + 12 * (self.CELL + self.GAP), self.height())

    def _weeks(self) -> int:
        return max(1, math.ceil(len(self.values) / 7))

    def _cell_size(self) -> float:
        # Fixed height (so the card never clips the bottom row); only shrinks
        # if the window is too narrow for twelve full-size weeks.
        available = (self.width() - self.LEFT) / self._weeks() - self.GAP
        return max(10.0, min(float(self.CELL), available))

    def _level_color(self, value: int, peak: int) -> QColor:
        if value <= 0 or peak <= 0:
            return QColor(EMPTY_CELL)  # a copy: the caller changes its alpha
        share = value / peak
        alpha = 70 if share < 0.25 else 125 if share < 0.5 else 185 if share < 0.75 else 255
        color = QColor(ACCENT)
        color.setAlpha(alpha)
        return color

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        cell = self._cell_size()
        step = cell + self.GAP
        weeks = self._weeks()
        peak = max(self.values, default=0)
        painter.setFont(QFont("Segoe UI", 7, QFont.DemiBold))
        painter.setPen(FAINT)
        for row, name in ((0, "Mon"), (2, "Wed"), (4, "Fri")):
            painter.drawText(
                QRectF(0, self.TOP + row * step, self.LEFT - 6, cell),
                Qt.AlignVCenter | Qt.AlignRight,
                name,
            )
        last_month = None
        last_label_x = -1000.0
        for col in range(weeks):
            week_start = self.start + timedelta(weeks=col)
            x = self.LEFT + col * step
            # A month name where a new month starts, but never squeezed on
            # top of the previous one.
            if week_start.month != last_month and x - last_label_x >= 34:
                last_month = week_start.month
                last_label_x = x
                painter.setPen(FAINT)
                painter.drawText(
                    QRectF(self.LEFT + col * step, 0, 40, 14),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    _MONTHS[week_start.month - 1],
                )
            # Columns fade in from left to right as the page opens.
            reveal = min(1.0, max(0.0, (self.progress * (weeks + 3) - col) / 3))
            for row in range(7):
                index = col * 7 + row
                if index >= len(self.values):
                    break
                color = self._level_color(self.values[index], peak)
                color.setAlpha(int(color.alpha() * reveal))
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
                painter.drawRoundedRect(
                    QRectF(self.LEFT + col * step, self.TOP + row * step, cell, cell), 3, 3
                )
        # Today gets a thin outline so "now" is easy to find.
        if self.values:
            index = len(self.values) - 1
            col, row = divmod(index, 7)
            painter.setPen(QPen(TEXT, 1.2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(
                QRectF(self.LEFT + col * step, self.TOP + row * step, cell, cell).adjusted(
                    -1.5, -1.5, 1.5, 1.5
                ),
                4,
                4,
            )

    def mouseMoveEvent(self, event) -> None:  # noqa: N802, ANN001
        cell = self._cell_size()
        step = cell + self.GAP
        pos = event.position()
        col = int((pos.x() - self.LEFT) // step)
        row = int((pos.y() - self.TOP) // step)
        index = col * 7 + row
        if pos.x() < self.LEFT or not (0 <= row < 7) or not (0 <= index < len(self.values)):
            QToolTip.hideText()
            return
        day = self.start + timedelta(days=index)
        words = self.values[index]
        text = f"{day:%a %d %b}: {words:,} word{'s' if words != 1 else ''}"
        QToolTip.showText(event.globalPosition().toPoint(), text, self)


class InsightsPage(QWidget):
    """The whole Insights page. Call refresh() whenever the history changes,
    with animate=True when the page is being opened."""

    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet(PAGE_STYLESHEET)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        outer.addWidget(scroll)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Insights")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        subtitle = _label("Counted on this PC only. Nothing leaves it.", "insightsSub")
        layout.addWidget(subtitle)

        # -- hero ---------------------------------------------------------
        self._hero = _HeroGlow()
        hero_layout = QVBoxLayout(self._hero)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        hero_layout.setSpacing(2)
        hero_layout.addWidget(_label("WORDS DICTATED", "insightsCaption"))
        self._total = _label("0", "insightsBig")
        hero_layout.addWidget(self._total)
        self._saved = _label("", "insightsSubStrong")
        hero_layout.addWidget(self._saved)
        self._saved_note = _label(
            f"Estimated against typing at {history.TYPING_WPM} words a minute, "
            "minus the time spent talking.",
            "insightsSub",
        )
        hero_layout.addWidget(self._saved_note)
        layout.addWidget(self._hero)

        # -- three small cards ---------------------------------------------
        row = QHBoxLayout()
        row.setSpacing(12)

        speed_card, speed = _card()
        speed.addWidget(_label("SPEAKING SPEED", "insightsCaption"))
        self._wpm, speed_value = self._value_with_unit("wpm")
        speed.addLayout(speed_value)
        self._speed_note = _label("", "insightsSub")
        speed.addWidget(self._speed_note)
        self._speed_bars = _SpeedBars()
        speed.addWidget(self._speed_bars)
        row.addWidget(speed_card, 1)

        streak_card, streak = _card()
        streak.addWidget(_label("DAY STREAK", "insightsCaption"))
        self._streak, streak_value = self._value_with_unit("days")
        self._streak_unit = streak_value.itemAt(1).widget()
        streak.addLayout(streak_value)
        streak.addWidget(_label("Days with a dictation, this week", "insightsSub"))
        self._dots = _WeekDots()
        streak.addWidget(self._dots)
        row.addWidget(streak_card, 1)

        today_card, today = _card()
        today.addWidget(_label("TODAY", "insightsCaption"))
        self._today, today_value = self._value_with_unit("words")
        today.addLayout(today_value)
        self._today_note = _label("", "insightsSub")
        today.addWidget(self._today_note)
        today.addStretch(1)
        row.addWidget(today_card, 1)
        layout.addLayout(row)

        # -- week chart --------------------------------------------------------
        week_card, week = _card()
        week.addWidget(_label("THIS WEEK", "insightsCaption"))
        self._week_chart = _WeekChart()
        week.addWidget(self._week_chart)
        layout.addWidget(week_card)

        # -- activity grid -----------------------------------------------------
        activity_card, activity = _card()
        header = QHBoxLayout()
        header.addWidget(_label(f"LAST {history.ACTIVITY_WEEKS} WEEKS", "insightsCaption"))
        header.addStretch(1)
        self._active_days = _label("", "insightsSub")
        header.addWidget(self._active_days)
        activity.addLayout(header)
        self._grid = _ActivityGrid()
        activity.addWidget(self._grid)
        legend = QHBoxLayout()
        legend.addStretch(1)
        legend.addWidget(_label("Less", "insightsSub"))
        for alpha in (0, 70, 125, 185, 255):
            swatch = QLabel()
            swatch.setFixedSize(11, 11)
            color = QColor(ACCENT)
            color.setAlpha(alpha)
            fill = EMPTY_CELL.name() if alpha == 0 else color.name(QColor.HexArgb)
            swatch.setStyleSheet(f"background: {fill}; border-radius: 3px;")
            legend.addWidget(swatch)
        legend.addWidget(_label("More", "insightsSub"))
        activity.addLayout(legend)
        # -- highlights, beside the grid -----------------------------------------
        highlights_card, highlights = _card()
        highlights.addWidget(_label("HIGHLIGHTS", "insightsCaption"))
        highlights.addSpacing(4)
        grid = QGridLayout()
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(2)
        self._longest = _label("", "insightsHighlightValue")
        self._busiest = _label("", "insightsHighlightValue")
        self._count = _label("", "insightsHighlightValue")
        for col, (value, caption) in enumerate(
            (
                (self._longest, "Longest dictation"),
                (self._busiest, "Most active hour"),
                (self._count, "Dictations in total"),
            )
        ):
            grid.addWidget(value, col * 3, 0)
            grid.addWidget(_label(caption, "insightsSub"), col * 3 + 1, 0)
            if col < 2:
                grid.setRowMinimumHeight(col * 3 + 2, 14)
        highlights.addLayout(grid)
        highlights.addStretch(1)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)
        bottom_row.addWidget(activity_card, 3)
        bottom_row.addWidget(highlights_card, 2)
        layout.addLayout(bottom_row)

        self._empty = _label(
            "Nothing to count yet. Hold your hotkey anywhere and talk, and your "
            "numbers show up here.",
            "insightsSub",
        )
        self._empty.setWordWrap(True)
        layout.addWidget(self._empty)
        layout.addStretch(1)

        self._content = [self._hero, speed_card, streak_card, today_card, week_card,
                         activity_card, highlights_card]
        self._anim: QVariantAnimation | None = None

    @staticmethod
    def _value_with_unit(unit: str) -> tuple[QLabel, QHBoxLayout]:
        line = QHBoxLayout()
        line.setSpacing(6)
        value = _label("0", "insightsValue")
        line.addWidget(value, 0, Qt.AlignBottom)
        line.addWidget(_label(unit, "insightsUnit"), 0, Qt.AlignBottom)
        line.addStretch(1)
        return value, line

    @staticmethod
    def _old_number(label: QLabel) -> int:
        try:
            return int(label.text().replace(",", ""))
        except ValueError:
            return 0

    def refresh(self, animate: bool = False) -> None:
        ins = history.compute_insights()
        empty = ins.dictations == 0
        for widget in self._content:
            widget.setVisible(not empty)
        self._empty.setVisible(empty)
        if empty:
            return

        for label, value, fmt in (
            (self._total, ins.total_words, "{:,}"),
            (self._wpm, ins.wpm, "{}"),
            (self._streak, ins.streak_days, "{}"),
            (self._today, ins.today_words, "{:,}"),
        ):
            count_up(label, 0 if animate else self._old_number(label), value, fmt)

        saved = history.format_minutes_saved(ins.minutes_saved)
        self._saved.setText(f"About {saved} of typing saved")
        if ins.wpm > history.TYPING_WPM:
            self._speed_note.setText(f"{ins.wpm / history.TYPING_WPM:.1f}x faster than typing")
        else:
            self._speed_note.setText("About the speed of typing")
        self._streak_unit.setText("day" if ins.streak_days == 1 else "days")
        self._today_note.setText(
            f"{ins.today_dictations} dictation{'s' if ins.today_dictations != 1 else ''} today"
            if ins.today_dictations
            else "Nothing yet today"
        )
        active = sum(1 for v in ins.activity if v)
        self._active_days.setText(f"{active} active day{'s' if active != 1 else ''}")
        self._longest.setText(f"{ins.longest_words:,} words, {round(ins.longest_seconds)} s")
        self._busiest.setText(
            f"Around {history.format_hour(ins.busiest_hour)}"
            if ins.busiest_hour is not None
            else "Not enough yet"
        )
        self._count.setText(f"{ins.dictations:,}")

        self._speed_bars.wpm = ins.wpm
        self._dots.active = ins.week_active
        self._dots.today = date.today()
        self._week_chart.values = ins.week
        self._week_chart.today = date.today()
        self._grid.start = ins.activity_start
        self._grid.values = ins.activity
        self._run_reveal(animate)

    def _run_reveal(self, animate: bool) -> None:
        if self._anim is not None:
            self._anim.stop()
        charts = (self._speed_bars, self._week_chart, self._grid)
        if not animate or not animations_enabled():
            for chart in charts:
                chart.progress = 1.0
                chart.update()
            self._dots.update()
            return

        def step(value: float) -> None:
            for chart in charts:
                chart.progress = value
                chart.update()

        anim = QVariantAnimation(self)
        anim.setDuration(1100)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.valueChanged.connect(step)
        self._anim = anim
        step(0.0)
        self._dots.update()
        anim.start()
