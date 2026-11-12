"""Project evaluation dashboard.

Fourth main view: period selector, KPI tiles, project distribution
donut, sortable project table with drilldown, and a stacked trend chart.
"""

import math
from datetime import date, datetime, timedelta
from typing import Any, Optional

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.database_protocol import DatabaseProtocol
from utils.project_stats import (
    aggregate_by_project,
    bucket_trend,
    compute_kpis,
    top_details_for_project,
)

from .theme import get_theme

UNASSIGNED_COLOR = "#95a5a6"
UNASSIGNED_LABEL = "Ohne Projekt"
MAX_DONUT_SEGMENTS = 10

PERIODS = [
    ("Diese Woche", "week"),
    ("Dieser Monat", "month"),
    ("Letzte 30 Tage", "30d"),
    ("Letzte 3 Monate", "90d"),
    ("Dieses Jahr", "year"),
    ("Gesamter Zeitraum", "all"),
]


def period_start(period_key: str, today: Optional[date] = None) -> Optional[datetime]:
    """Start datetime for a dashboard period key (None = no limit)."""
    today = today or date.today()

    if period_key == "week":
        start_day = today - timedelta(days=today.weekday())
    elif period_key == "month":
        start_day = today.replace(day=1)
    elif period_key == "30d":
        start_day = today - timedelta(days=30)
    elif period_key == "90d":
        start_day = today - timedelta(days=90)
    elif period_key == "year":
        start_day = today.replace(month=1, day=1)
    else:
        return None

    return datetime.combine(start_day, datetime.min.time())


class DonutChart(QWidget):
    """Donut chart of time distribution with hover tooltips."""

    def __init__(self):
        super().__init__()
        self.theme = get_theme()
        self.segments: list[tuple[str, int, QColor]] = []
        self.total_seconds = 0
        self._angle_ranges: list[tuple[float, float, str, int]] = []
        self.setMinimumSize(300, 300)
        self.setMouseTracking(True)

    def set_data(self, segments: list[tuple[str, int, QColor]]) -> None:
        """Set (label, seconds, color) segments, ordered by size."""
        self.segments = segments
        self.total_seconds = sum(s[1] for s in segments)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = self.theme.colors
        painter.fillRect(self.rect(), QColor(colors.background))
        self._angle_ranges = []

        side = min(self.width(), self.height()) - 24
        if side < 80:
            return

        outer = QRect(
            (self.width() - side) // 2, (self.height() - side) // 2, side, side
        )

        if not self.segments or self.total_seconds == 0:
            painter.setPen(QPen(QColor(colors.text_muted), 1))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Keine Daten"
            )
            return

        # Segments start at 12 o'clock, clockwise
        start_angle = 90.0
        for label, seconds, color in self.segments:
            span = seconds / self.total_seconds * 360.0
            painter.setPen(QPen(QColor(colors.background), 2))
            painter.setBrush(color)
            painter.drawPie(
                outer, int(start_angle * 16), int(-span * 16)
            )
            self._angle_ranges.append((start_angle, span, label, seconds))
            start_angle -= span

        # Punch the hole for the donut
        hole_ratio = 0.62
        hole_side = int(side * hole_ratio)
        hole = QRect(
            (self.width() - hole_side) // 2,
            (self.height() - hole_side) // 2,
            hole_side, hole_side,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors.background))
        painter.drawEllipse(hole)

        # Total in the middle
        painter.setPen(QPen(QColor(colors.text_primary), 1))
        painter.setFont(QFont('Segoe UI', 15, QFont.Weight.Bold))
        painter.drawText(
            hole.adjusted(0, -12, 0, -12), Qt.AlignmentFlag.AlignCenter,
            f"{self.total_seconds / 3600:.1f}h",
        )
        painter.setFont(QFont('Segoe UI', 9))
        painter.setPen(QPen(QColor(colors.text_muted), 1))
        painter.drawText(
            hole.adjusted(0, 22, 0, 22), Qt.AlignmentFlag.AlignCenter,
            "aktiv",
        )

    def mouseMoveEvent(self, event):
        segment = self._segment_at(event.pos().x(), event.pos().y())
        if segment:
            label, seconds = segment
            share = seconds / self.total_seconds * 100 if self.total_seconds else 0
            self.setToolTip(f"{label}: {seconds / 3600:.1f}h ({share:.0f}%)")
        else:
            self.setToolTip("")

    def _segment_at(self, x: int, y: int) -> Optional[tuple[str, int]]:
        """Segment under the cursor, or None outside the ring."""
        side = min(self.width(), self.height()) - 24
        cx, cy = self.width() / 2, self.height() / 2
        dx, dy = x - cx, cy - y  # invert y for math angles

        dist = math.hypot(dx, dy)
        if not (side / 2 * 0.62 <= dist <= side / 2):
            return None

        angle = math.degrees(math.atan2(dy, dx)) % 360

        for start, span, label, seconds in self._angle_ranges:
            # Clockwise from start: covered range is (start - span, start]
            delta = (start - angle) % 360
            if 0 <= delta < span:
                return label, seconds
        return None


class TrendChart(QWidget):
    """Stacked bars of project time per week or month bucket."""

    LEFT_MARGIN = 45
    RIGHT_MARGIN = 15
    TOP_MARGIN = 18
    BOTTOM_MARGIN = 32

    def __init__(self):
        super().__init__()
        self.theme = get_theme()
        self.labels: list[str] = []
        self.buckets: list[dict[Any, int]] = []
        self.color_lookup: dict[Any, QColor] = {}
        self.name_lookup: dict[Any, str] = {}
        self._segment_rects: list[tuple[QRect, str]] = []
        self.setMinimumHeight(210)
        self.setMouseTracking(True)

    def set_data(self, labels, buckets, color_lookup, name_lookup) -> None:
        self.labels = labels
        self.buckets = buckets
        self.color_lookup = color_lookup
        self.name_lookup = name_lookup
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = self.theme.colors
        painter.fillRect(self.rect(), QColor(colors.background))
        self._segment_rects = []

        if not self.buckets:
            painter.setPen(QPen(QColor(colors.text_muted), 1))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Keine Daten"
            )
            return

        left = self.LEFT_MARGIN
        right = self.width() - self.RIGHT_MARGIN
        top = self.TOP_MARGIN
        bottom = self.height() - self.BOTTOM_MARGIN
        height = bottom - top

        max_seconds = max(
            (sum(bucket.values()) for bucket in self.buckets), default=0
        )
        if max_seconds == 0:
            return
        max_hours = max(1.0, math.ceil(max_seconds / 3600))

        # Reference lines at 0%, 50%, 100%
        painter.setFont(QFont('Segoe UI', 8))
        for fraction in (0.0, 0.5, 1.0):
            y = int(bottom - fraction * height)
            painter.setPen(QPen(QColor(colors.border_light), 1))
            painter.drawLine(left, y, right, y)
            painter.setPen(QPen(QColor(colors.text_muted), 1))
            painter.drawText(
                2, y - 8, self.LEFT_MARGIN - 8, 16,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{fraction * max_hours:.0f}h",
            )

        col_width = (right - left) / len(self.buckets)
        bar_width = max(col_width * 0.6, 3)
        label_step = max(1, math.ceil(len(self.labels) / 12))

        for i, bucket in enumerate(self.buckets):
            col_x = left + i * col_width
            bar_x = col_x + (col_width - bar_width) / 2

            stacked = sorted(bucket.items(), key=lambda x: x[1], reverse=True)
            y_cursor = float(bottom)

            for key, seconds in stacked:
                seg_height = max(seconds / 3600 / max_hours * height, 1)
                rect = QRect(
                    int(bar_x), int(y_cursor - seg_height),
                    int(bar_width), int(seg_height),
                )
                painter.fillRect(
                    rect, self.color_lookup.get(key, QColor(UNASSIGNED_COLOR))
                )
                name = self.name_lookup.get(key, UNASSIGNED_LABEL)
                self._segment_rects.append(
                    (rect, f"{self.labels[i]} – {name}: {seconds / 3600:.1f}h")
                )
                y_cursor -= seg_height

            if i % label_step == 0:
                painter.setPen(QPen(QColor(colors.text_secondary), 1))
                painter.drawText(
                    int(col_x), bottom + 4, int(col_width), 20,
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    self.labels[i],
                )

    def mouseMoveEvent(self, event):
        for rect, tooltip in self._segment_rects:
            if rect.contains(event.pos()):
                self.setToolTip(tooltip)
                return
        self.setToolTip("")


class DashboardView(QWidget):
    """Project evaluation view combining KPIs, charts, and drilldown."""

    def __init__(self, database: DatabaseProtocol):
        super().__init__()
        self.database = database
        self.theme = get_theme()
        self._activities: list[dict] = []
        self._row_project_ids: list[Any] = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header row: period selector + KPI tiles
        header = QHBoxLayout()

        header.addWidget(QLabel("Zeitraum:"))
        self.period_combo = QComboBox()
        for label, key in PERIODS:
            self.period_combo.addItem(label, key)
        self.period_combo.setCurrentIndex(1)  # Dieser Monat
        self.period_combo.currentIndexChanged.connect(self.refresh)
        header.addWidget(self.period_combo)

        header.addStretch()

        self.kpi_labels: dict[str, QLabel] = {}
        for key, title in (
            ("active", "Aktive Zeit"),
            ("avg", "Ø pro Arbeitstag"),
            ("assigned", "Zugeordnet"),
            ("busiest", "Aktivster Tag"),
        ):
            header.addWidget(self._create_kpi_card(key, title))

        layout.addLayout(header)

        # Middle row: donut | table + details
        middle = QHBoxLayout()

        self.donut = DonutChart()
        self.donut.setFixedWidth(320)
        middle.addWidget(self.donut)

        right_column = QVBoxLayout()

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Projekt", "Zeit (h)", "Anteil %", "Aktivitäten", "Tage", "Ø h/Tag"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._update_details)
        right_column.addWidget(self.table, stretch=3)

        self.details_label = QLabel("Projekt in der Tabelle wählen für Details")
        self.details_label.setProperty("class", "muted")
        self.details_label.setWordWrap(True)
        self.details_label.setTextFormat(Qt.TextFormat.RichText)
        self.details_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        details_frame = QFrame()
        details_frame.setProperty("class", "card")
        details_layout = QVBoxLayout(details_frame)
        details_layout.addWidget(self.details_label)
        right_column.addWidget(details_frame, stretch=2)

        middle.addLayout(right_column, stretch=1)
        layout.addLayout(middle, stretch=1)

        # Bottom: trend chart
        trend_title = QLabel("Verlauf")
        trend_title.setProperty("class", "subtitle")
        layout.addWidget(trend_title)

        self.trend = TrendChart()
        layout.addWidget(self.trend)

    def _create_kpi_card(self, key: str, title: str) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        card.setMinimumWidth(140)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setProperty("class", "muted")
        title_font = QFont('Segoe UI', 8)
        title_label.setFont(title_font)
        card_layout.addWidget(title_label)

        value_label = QLabel("–")
        value_font = QFont('Segoe UI', 13)
        value_font.setBold(True)
        value_label.setFont(value_font)
        card_layout.addWidget(value_label)

        self.kpi_labels[key] = value_label
        return card

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload all dashboard data for the selected period."""
        start = period_start(self.period_combo.currentData())
        end = datetime.combine(date.today(), datetime.max.time())

        self._activities = self.database.get_activities(
            start_date=start, end_date=end
        )
        projects = self.database.get_projects()
        project_map = {p['id']: p for p in projects}

        self._update_kpis()
        stats = aggregate_by_project(self._activities)
        self._update_donut(stats, project_map)
        self._update_table(stats, project_map)
        self._update_trend(project_map)
        self._update_details()

    def _project_name(self, key: Any, project_map: dict) -> str:
        if key is None:
            return UNASSIGNED_LABEL
        project = project_map.get(key)
        return project['name'] if project else f"Projekt {key}"

    def _project_color(self, key: Any, project_map: dict) -> QColor:
        if key is None:
            return QColor(UNASSIGNED_COLOR)
        project = project_map.get(key)
        if project and project.get('color'):
            return QColor(project['color'])
        return QColor(UNASSIGNED_COLOR)

    def _update_kpis(self):
        kpis = compute_kpis(self._activities)

        self.kpi_labels["active"].setText(
            f"{kpis['active_seconds'] / 3600:.1f}h"
        )
        self.kpi_labels["avg"].setText(
            f"{kpis['avg_seconds_per_day'] / 3600:.1f}h"
            f"  ({kpis['days_with_data']} Tage)"
        )
        self.kpi_labels["assigned"].setText(
            f"{kpis['assigned_ratio'] * 100:.0f}%"
        )

        busiest = kpis['busiest_day']
        if busiest:
            self.kpi_labels["busiest"].setText(
                f"{busiest[0].strftime('%d.%m.')} ({busiest[1] / 3600:.1f}h)"
            )
        else:
            self.kpi_labels["busiest"].setText("–")

    def _update_donut(self, stats: dict, project_map: dict):
        ordered = sorted(
            stats.items(), key=lambda x: x[1]['seconds'], reverse=True
        )

        segments = []
        rest_seconds = 0
        for i, (key, entry) in enumerate(ordered):
            if i < MAX_DONUT_SEGMENTS - 1:
                segments.append((
                    self._project_name(key, project_map),
                    entry['seconds'],
                    self._project_color(key, project_map),
                ))
            else:
                rest_seconds += entry['seconds']

        if rest_seconds > 0:
            segments.append(
                ("Übrige", rest_seconds, QColor(UNASSIGNED_COLOR).darker(120))
            )

        self.donut.set_data(segments)

    def _update_table(self, stats: dict, project_map: dict):
        total_seconds = sum(e['seconds'] for e in stats.values())

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self._row_project_ids = []

        ordered = sorted(
            stats.items(), key=lambda x: x[1]['seconds'], reverse=True
        )

        for key, entry in ordered:
            row = self.table.rowCount()
            self.table.insertRow(row)

            hours = entry['seconds'] / 3600
            share = entry['seconds'] / total_seconds * 100 if total_seconds else 0
            days = len(entry['days'])
            avg_per_day = hours / days if days else 0

            name_item = QTableWidgetItem(self._project_name(key, project_map))
            name_item.setData(
                Qt.ItemDataRole.DecorationRole,
                self._project_color(key, project_map),
            )
            name_item.setData(Qt.ItemDataRole.UserRole, key)
            self.table.setItem(row, 0, name_item)

            for col, value in (
                (1, round(hours, 1)),
                (2, round(share, 1)),
                (3, entry['count']),
                (4, days),
                (5, round(avg_per_day, 1)),
            ):
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.DisplayRole, value)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(row, col, item)

        self.table.setSortingEnabled(True)
        self.table.sortItems(1, Qt.SortOrder.DescendingOrder)

    def _update_trend(self, project_map: dict):
        labels, buckets, _mode = bucket_trend(self._activities)

        keys = {key for bucket in buckets for key in bucket}
        color_lookup = {k: self._project_color(k, project_map) for k in keys}
        name_lookup = {k: self._project_name(k, project_map) for k in keys}

        self.trend.set_data(labels, buckets, color_lookup, name_lookup)

    def _update_details(self):
        """Show top apps and contents for the selected table row."""
        selected = self.table.selectedItems()
        if not selected:
            self.details_label.setText(
                "Projekt in der Tabelle wählen für Details"
            )
            return

        name_item = self.table.item(selected[0].row(), 0)
        project_id = name_item.data(Qt.ItemDataRole.UserRole)
        project_name = name_item.text()

        top_apps, top_contents = top_details_for_project(
            self._activities, project_id
        )

        html = f"<b>Details: {project_name}</b><br>"
        html += "<table width='100%'><tr>"

        for title, entries in (
            ("Top Apps", top_apps),
            ("Top Inhalte", top_contents),
        ):
            html += f"<td valign='top' width='50%'><i>{title}</i><br>"
            if entries:
                for entry_name, seconds in entries:
                    display = (
                        entry_name if len(entry_name) <= 45
                        else entry_name[:42] + "..."
                    )
                    html += f"{display} – {seconds / 3600:.1f}h<br>"
            else:
                html += "–<br>"
            html += "</td>"

        html += "</tr></table>"
        self.details_label.setText(html)
