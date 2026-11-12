"""Week and month overview widgets.

Both widgets receive pre-aggregated data from the main window and
render stacked bars (week) or a heatmap grid (month). Clicking a day
switches back to the day view.
"""

import calendar
import math
from datetime import date, timedelta
from typing import Any

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from .theme import contrasting_text_color, get_theme

UNASSIGNED_KEY = None
UNASSIGNED_COLOR = "#95a5a6"

WEEKDAY_LABELS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']


class WeekView(QWidget):
    """Stacked bar chart of project time per weekday.

    Signals:
        day_clicked: Emitted with the clicked date
    """

    day_clicked = pyqtSignal(object)

    LEFT_MARGIN = 55
    RIGHT_MARGIN = 20
    TOP_MARGIN = 30
    BOTTOM_MARGIN = 90

    def __init__(self):
        super().__init__()
        self.theme = get_theme()
        self.monday: date = date.today()
        self.day_project_seconds: dict[date, dict[Any, int]] = {}
        self.project_map: dict[int, dict[str, Any]] = {}
        self._segment_rects: list[tuple[QRect, str]] = []
        self._day_columns: list[tuple[QRect, date]] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(320)

    def set_data(
        self,
        monday: date,
        day_project_seconds: dict[date, dict[Any, int]],
        project_map: dict[int, dict[str, Any]],
    ) -> None:
        """Set aggregated data: per day a mapping of project_id -> seconds."""
        self.monday = monday
        self.day_project_seconds = day_project_seconds
        self.project_map = project_map
        self.update()

    def _project_name(self, key) -> str:
        if key is UNASSIGNED_KEY:
            return "Ohne Projekt"
        project = self.project_map.get(key)
        return project['name'] if project else f"Projekt {key}"

    def _project_color(self, key) -> QColor:
        if key is UNASSIGNED_KEY:
            return QColor(UNASSIGNED_COLOR)
        project = self.project_map.get(key)
        if project and project.get('color'):
            return QColor(project['color'])
        return QColor(UNASSIGNED_COLOR)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = self.theme.colors
        painter.fillRect(self.rect(), QColor(colors.background))

        self._segment_rects = []
        self._day_columns = []

        chart_left = self.LEFT_MARGIN
        chart_right = self.width() - self.RIGHT_MARGIN
        chart_top = self.TOP_MARGIN
        chart_bottom = self.height() - self.BOTTOM_MARGIN
        chart_height = chart_bottom - chart_top

        if chart_height < 50 or chart_right - chart_left < 100:
            return

        days = [self.monday + timedelta(days=i) for i in range(7)]
        day_totals = {
            d: sum(self.day_project_seconds.get(d, {}).values()) for d in days
        }
        max_hours = max(8.0, math.ceil(max(day_totals.values(), default=0) / 3600))

        self._draw_grid(painter, chart_left, chart_right, chart_top,
                        chart_bottom, chart_height, max_hours)
        self._draw_bars(painter, days, day_totals, chart_left, chart_right,
                        chart_top, chart_bottom, chart_height, max_hours)
        self._draw_legend(painter, days, chart_left, chart_right)

    def _draw_grid(self, painter, left, right, top, bottom, height, max_hours):
        colors = self.theme.colors
        grid_pen = QPen(QColor(colors.border_light), 1)
        text_pen = QPen(QColor(colors.text_muted), 1)
        painter.setFont(QFont('Segoe UI', 8))

        step = 2 if max_hours <= 14 else 4
        for h in range(0, int(max_hours) + 1, step):
            y = int(bottom - h / max_hours * height)
            painter.setPen(grid_pen)
            painter.drawLine(left, y, right, y)
            painter.setPen(text_pen)
            painter.drawText(
                5, y - 8, self.LEFT_MARGIN - 12, 16,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{h}h",
            )

    def _draw_bars(self, painter, days, day_totals, left, right, top,
                   bottom, height, max_hours):
        colors = self.theme.colors
        col_width = (right - left) / 7
        today = date.today()

        painter.setFont(QFont('Segoe UI', 9))

        for i, day in enumerate(days):
            col_x = left + i * col_width
            self._day_columns.append(
                (QRect(int(col_x), top, int(col_width), bottom - top + 40), day)
            )

            # Day label below the axis
            is_today = day == today
            label_color = colors.accent if is_today else colors.text_secondary
            painter.setPen(QPen(QColor(label_color), 1))
            font = QFont('Segoe UI', 9)
            font.setBold(is_today)
            painter.setFont(font)
            painter.drawText(
                int(col_x), bottom + 6, int(col_width), 30,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                f"{WEEKDAY_LABELS[i]}\n{day.strftime('%d.%m.')}",
            )

            segments = self.day_project_seconds.get(day, {})
            if not segments:
                continue

            bar_width = col_width * 0.62
            bar_x = col_x + (col_width - bar_width) / 2

            # Largest project at the bottom of the stack
            stacked = sorted(segments.items(), key=lambda x: x[1], reverse=True)

            y_cursor = float(bottom)
            for key, seconds in stacked:
                seg_height = seconds / 3600 / max_hours * height
                if seg_height < 1:
                    seg_height = 1

                rect = QRect(
                    int(bar_x), int(y_cursor - seg_height),
                    int(bar_width), int(seg_height),
                )
                color = self._project_color(key)
                painter.fillRect(rect, color)

                hours = seconds / 3600
                tooltip = f"{self._project_name(key)}: {hours:.1f}h"
                self._segment_rects.append((rect, tooltip))

                y_cursor -= seg_height

            # Total above the bar
            total_hours = day_totals[day] / 3600
            painter.setPen(QPen(QColor(colors.text_primary), 1))
            painter.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
            painter.drawText(
                int(col_x), int(y_cursor) - 18, int(col_width), 16,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                f"{total_hours:.1f}h",
            )

    def _draw_legend(self, painter, days, left, right):
        """Draw a legend of the week's top projects below the chart."""
        colors = self.theme.colors

        week_totals: dict[Any, int] = {}
        for day in days:
            for key, seconds in self.day_project_seconds.get(day, {}).items():
                week_totals[key] = week_totals.get(key, 0) + seconds

        if not week_totals:
            painter.setPen(QPen(QColor(colors.text_muted), 1))
            painter.setFont(QFont('Segoe UI', 10))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                "Keine Aktivitäten in dieser Woche",
            )
            return

        top_projects = sorted(
            week_totals.items(), key=lambda x: x[1], reverse=True
        )[:8]

        painter.setFont(QFont('Segoe UI', 8))
        metrics = painter.fontMetrics()

        x = left
        y = self.height() - 24

        for key, seconds in top_projects:
            name = self._project_name(key)
            entry_text = f"{name} ({seconds / 3600:.1f}h)"
            entry_width = 16 + metrics.horizontalAdvance(entry_text) + 16

            if x + entry_width > right:
                break

            painter.fillRect(QRect(int(x), y, 10, 10), self._project_color(key))
            painter.setPen(QPen(QColor(colors.text_secondary), 1))
            painter.drawText(
                int(x) + 14, y - 2, int(entry_width), 14,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                entry_text,
            )
            x += entry_width

    def mouseMoveEvent(self, event):
        for rect, tooltip in self._segment_rects:
            if rect.contains(event.pos()):
                self.setToolTip(tooltip)
                return
        self.setToolTip("")

    def mouseDoubleClickEvent(self, event):
        for rect, day in self._day_columns:
            if rect.contains(event.pos()):
                self.day_clicked.emit(day)
                return


class MonthView(QWidget):
    """Calendar heatmap of active time per day.

    Signals:
        day_clicked: Emitted with the clicked date
    """

    day_clicked = pyqtSignal(object)

    MARGIN = 20
    HEADER_HEIGHT = 30

    def __init__(self):
        super().__init__()
        self.theme = get_theme()
        self.first_day: date = date.today().replace(day=1)
        self.day_seconds: dict[date, int] = {}
        self._day_cells: list[tuple[QRect, date]] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(320)

    def set_data(self, first_day: date, day_seconds: dict[date, int]) -> None:
        """Set aggregated active seconds per day for one month."""
        self.first_day = first_day.replace(day=1)
        self.day_seconds = day_seconds
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = self.theme.colors
        painter.fillRect(self.rect(), QColor(colors.background))

        self._day_cells = []

        year, month = self.first_day.year, self.first_day.month
        weeks = calendar.Calendar().monthdatescalendar(year, month)

        grid_left = self.MARGIN
        grid_top = self.MARGIN + self.HEADER_HEIGHT
        grid_width = self.width() - 2 * self.MARGIN
        grid_height = self.height() - grid_top - self.MARGIN

        if grid_width < 100 or grid_height < 100:
            return

        cell_width = grid_width / 7
        cell_height = grid_height / len(weeks)

        # Weekday header
        painter.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(colors.text_secondary), 1))
        for i, label in enumerate(WEEKDAY_LABELS):
            painter.drawText(
                int(grid_left + i * cell_width), self.MARGIN,
                int(cell_width), self.HEADER_HEIGHT,
                Qt.AlignmentFlag.AlignCenter, label,
            )

        max_seconds = max(
            (s for d, s in self.day_seconds.items() if d.month == month),
            default=0,
        )
        accent = QColor(colors.accent)
        today = date.today()

        for row, week in enumerate(weeks):
            for col, day in enumerate(week):
                if day.month != month:
                    continue

                cell = QRect(
                    int(grid_left + col * cell_width + 2),
                    int(grid_top + row * cell_height + 2),
                    int(cell_width - 4),
                    int(cell_height - 4),
                )
                self._day_cells.append((cell, day))

                seconds = self.day_seconds.get(day, 0)

                # Heat color: accent with intensity by hours
                if seconds > 0 and max_seconds > 0:
                    alpha = int(40 + 200 * (seconds / max_seconds))
                    fill = QColor(accent)
                    fill.setAlpha(min(alpha, 255))
                else:
                    fill = QColor(colors.background_secondary)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(fill))
                painter.drawRoundedRect(cell, 6, 6)

                if day == today:
                    painter.setPen(QPen(QColor(colors.error), 2))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(cell, 6, 6)

                # Day number
                text_color = (
                    contrasting_text_color(fill) if seconds > 0
                    else QColor(colors.text_muted)
                )
                painter.setPen(QPen(text_color, 1))
                painter.setFont(QFont('Segoe UI', 8))
                painter.drawText(
                    cell.adjusted(6, 4, -4, -4),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                    str(day.day),
                )

                # Hours
                if seconds > 0:
                    painter.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
                    painter.drawText(
                        cell, Qt.AlignmentFlag.AlignCenter,
                        f"{seconds / 3600:.1f}h",
                    )

    def mouseMoveEvent(self, event):
        for rect, day in self._day_cells:
            if rect.contains(event.pos()):
                seconds = self.day_seconds.get(day, 0)
                self.setToolTip(
                    f"{day.strftime('%d.%m.%Y')}: {seconds / 3600:.1f}h aktiv"
                )
                return
        self.setToolTip("")

    def mouseDoubleClickEvent(self, event):
        for rect, day in self._day_cells:
            if rect.contains(event.pos()):
                self.day_clicked.emit(day)
                return
