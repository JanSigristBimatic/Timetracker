import hashlib
import json
import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Optional

from PyQt6.QtCore import QMimeData, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor, QDrag, QFont, QPainter, QPen
from PyQt6.QtWidgets import QMenu, QMessageBox, QRubberBand, QWidget

from core.database_protocol import DatabaseProtocol
from utils.activity_merger import merge_activities
from utils.config import get_env_int, should_ignore_activity
from utils.icon_cache import IconCache
from .theme import contrasting_text_color, get_theme

logger = logging.getLogger(__name__)

DRAG_START_DISTANCE = 10


class TimelineWidget(QWidget):
    """Widget to display activity timeline.

    Signals:
        data_changed: Activities were assigned or deleted; reload needed
        undoable_action: Emitted with an undo record before data_changed
        manual_entry_requested: Double click on empty space (datetime)
        zoom_changed: Zoom level changed internally (pixels per hour)
    """

    data_changed = pyqtSignal()
    undoable_action = pyqtSignal(dict)
    manual_entry_requested = pyqtSignal(object)
    zoom_changed = pyqtSignal(int)

    def __init__(self, database: DatabaseProtocol):
        super().__init__()
        self.database = database
        self.activities: list[dict[str, Any]] = []
        self.current_date = datetime.now().date()
        self.theme = get_theme()

        # Icon cache
        self.icon_cache = IconCache()

        # Merge settings from environment
        self.reload_settings()

        # Visual settings
        self.hour_height = 60  # pixels per hour (adjustable via zoom)
        self.left_margin = 60
        self.right_margin = 20
        self.top_margin = 20

        # Colors - from theme
        self._update_colors()

        # Color palette for different apps
        self.app_colors: dict[str, QColor] = {}

        # Predefined color palette for better distinction (30 colors)
        self.color_palette = [
            QColor(52, 152, 219),   # Blue
            QColor(46, 204, 113),   # Green
            QColor(155, 89, 182),   # Purple
            QColor(241, 196, 15),   # Yellow
            QColor(230, 126, 34),   # Orange
            QColor(231, 76, 60),    # Red
            QColor(26, 188, 156),   # Turquoise
            QColor(52, 73, 94),     # Dark Blue
            QColor(22, 160, 133),   # Sea Green
            QColor(243, 156, 18),   # Bright Orange
            QColor(211, 84, 0),     # Dark Orange
            QColor(192, 57, 43),    # Dark Red
            QColor(142, 68, 173),   # Dark Purple
            QColor(41, 128, 185),   # Ocean Blue
            QColor(39, 174, 96),    # Emerald
            QColor(127, 140, 141),  # Gray
            QColor(44, 62, 80),     # Midnight Blue
            QColor(149, 165, 166),  # Silver
            QColor(236, 240, 241),  # Clouds
            QColor(189, 195, 199),  # Concrete
            QColor(255, 118, 117),  # Light Red
            QColor(253, 203, 110),  # Light Orange
            QColor(162, 155, 254),  # Light Purple
            QColor(116, 185, 255),  # Light Blue
            QColor(9, 132, 227),    # Dodger Blue
            QColor(108, 92, 231),   # Blue Violet
            QColor(255, 159, 243),  # Pink
            QColor(85, 239, 196),   # Aqua
            QColor(0, 184, 148),    # Green Sea
            QColor(255, 234, 167),  # Light Yellow
        ]

        # Track activity rectangles for click detection
        self.activity_rects: list[tuple[QRect, dict]] = []

        # Multi-selection state
        self.selected_activities: list[dict] = []
        self.last_clicked_activity: Optional[dict] = None

        self.setMinimumHeight(24 * self.hour_height + 2 * self.top_margin)
        self.setMouseTracking(True)
        self.setToolTip("")

        # Drag and rubber band state
        self.drag_start_position = None
        self._press_on_activity = False
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._rubber_origin = None

        self._cached_projects: dict[int, dict] = {}

    def reload_settings(self) -> None:
        """Reload merge settings from environment variables."""
        self.merge_gap = get_env_int('MERGE_GAP', 60)
        self.min_activity_duration = get_env_int('MIN_ACTIVITY_DURATION', 10)
        self.project_merge_gap = get_env_int('PROJECT_MERGE_GAP', 180)

    def _update_colors(self):
        """Update colors from theme"""
        self.colors = self.theme.get_timeline_colors()

    def set_activities(self, activities, current_date):
        """Set activities to display, preserving the current selection."""
        selected_keys = {self._activity_key(a) for a in self.selected_activities}

        # Filter out ignored processes
        filtered = [
            act for act in activities
            if not should_ignore_activity(act['app_name'], act.get('window_title', ''))
        ]

        self.activities = merge_activities(
            filtered,
            min_duration=self.min_activity_duration,
            merge_gap=self.merge_gap,
            project_merge_gap=self.project_merge_gap,
        )
        self.current_date = current_date

        # Restore selection across refreshes (keyed by start time + app)
        self.selected_activities = [
            a for a in self.activities if self._activity_key(a) in selected_keys
        ]

        # Cache projects for paint performance (avoids DB query per activity)
        self._cached_projects = {
            p['id']: p for p in self.database.get_projects()
        }

        self.update()

    @staticmethod
    def _activity_key(activity: dict) -> tuple:
        """Stable identity of a merged block across reloads."""
        return (activity['timestamp'], activity['app_name'])

    def set_zoom(self, hour_height):
        """Set zoom level (pixels per hour)"""
        self.hour_height = hour_height
        self.setMinimumHeight(24 * self.hour_height + 2 * self.top_margin)
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        """Paint the timeline"""
        self._update_colors()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), self.colors['background'])

        self.draw_time_grid(painter)
        self.draw_activities(painter)
        self.draw_now_line(painter)

    def draw_time_grid(self, painter):
        """Draw time grid (hours)"""
        painter.setPen(QPen(self.colors['grid'], 1))
        font = QFont('Segoe UI', 9)
        painter.setFont(font)

        width = self.width()

        for hour in range(25):  # 0-24
            y = self.top_margin + hour * self.hour_height

            painter.drawLine(self.left_margin, y, width - self.right_margin, y)

            time_str = f"{hour:02d}:00"
            painter.setPen(QPen(self.colors['text'], 1))
            painter.drawText(10, y - 5, self.left_margin - 15, 20,
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                           time_str)
            painter.setPen(QPen(self.colors['grid'], 1))

    def draw_now_line(self, painter):
        """Draw a marker line at the current time (today only)."""
        if self.current_date != date.today():
            return

        now = datetime.now()
        hours_from_midnight = now.hour + now.minute / 60 + now.second / 3600
        y = int(self.top_margin + hours_from_midnight * self.hour_height)

        now_color = self.theme.get_qcolor('error')
        painter.setPen(QPen(now_color, 2))
        painter.drawLine(self.left_margin, y, self.width() - self.right_margin, y)

        painter.setBrush(QBrush(now_color))
        painter.drawEllipse(self.left_margin - 4, y - 4, 8, 8)

    def now_line_y(self) -> Optional[int]:
        """Y position of the current-time marker, or None if not today."""
        if self.current_date != date.today():
            return None
        now = datetime.now()
        hours = now.hour + now.minute / 60
        return int(self.top_margin + hours * self.hour_height)

    def _color_for_activity(self, activity: dict) -> QColor:
        """Determine the block color (project color, app color, or idle)."""
        if activity.get('is_idle', False):
            return self.colors['idle']

        if activity.get('project_id'):
            project = self._cached_projects.get(activity['project_id'])
            if project and project.get('color'):
                return QColor(project['color'])

        app_name = activity['app_name']
        if app_name not in self.app_colors:
            hash_val = int(hashlib.md5(app_name.encode()).hexdigest()[:8], 16)
            base_color = self.color_palette[hash_val % len(self.color_palette)]

            # If color already used, slightly shift hue for distinction
            if base_color in self.app_colors.values():
                h, s, v, a = base_color.getHsv()
                self.app_colors[app_name] = QColor.fromHsv((h + 20) % 360, s, v, a)
            else:
                self.app_colors[app_name] = base_color

        return self.app_colors[app_name]

    def draw_activities(self, painter):
        """Draw activity blocks"""
        self.activity_rects = []

        if not self.activities:
            return

        width = self.width()
        timeline_width = width - self.left_margin - self.right_margin
        bottom_limit = self.top_margin + 24 * self.hour_height

        for activity in self.activities:
            timestamp = activity['timestamp']
            duration = activity['duration']

            hours_from_midnight = (
                timestamp.hour +
                timestamp.minute / 60 +
                timestamp.second / 3600
            )

            y = self.top_margin + hours_from_midnight * self.hour_height
            height = max(duration / 3600 * self.hour_height, 3)

            # Clip blocks that would extend past midnight
            if y + height > bottom_limit:
                height = bottom_limit - y

            rect = QRect(self.left_margin, int(y), timeline_width, int(height))

            is_idle = activity.get('is_idle', False)
            color = self._color_for_activity(activity)

            if is_idle:
                # Hatched fill makes idle periods visually distinct
                painter.fillRect(rect, QBrush(color, Qt.BrushStyle.BDiagPattern))
            else:
                painter.fillRect(rect, color)

            # Border (highlighted if selected)
            if activity in self.selected_activities:
                painter.setPen(QPen(self.colors['selected_border'], 3))
            else:
                painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
            painter.drawRect(rect)

            self.activity_rects.append((rect, activity))

            if height > 15:
                self._draw_activity_label(painter, rect, activity, color, height)

    def _draw_activity_label(self, painter, rect, activity, color, height):
        """Draw icon and text inside an activity block."""
        text_offset = 5

        if activity.get('process_path'):
            icon_pixmap = self.icon_cache.get_icon_pixmap(
                activity['process_path'], size=16
            )
            if icon_pixmap and not icon_pixmap.isNull():
                scaled_icon = icon_pixmap.scaled(
                    14, 14,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                painter.drawPixmap(rect.x() + 3, rect.y() + 2, scaled_icon)
                text_offset = 20

        # Readable text color depending on block brightness
        painter.setPen(QPen(contrasting_text_color(color), 1))
        painter.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))

        app_name = activity['app_name']
        window_title = activity['window_title'] or ''

        project_name = ''
        if activity.get('project_id'):
            project = self._cached_projects.get(activity['project_id'])
            if project:
                project_name = project['name']

        if height > 40:
            text = f"{app_name}"
            if project_name:
                text += f"\n[{project_name}]"
            if window_title:
                text += f"\n{window_title[:40]}"
        elif height > 25:
            text = f"{app_name}"
            if project_name:
                text += f" [{project_name}]"
        else:
            text = app_name[:20]

        painter.drawText(
            rect.adjusted(text_offset, 2, -5, -2),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            text
        )

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def wheelEvent(self, event):
        """Ctrl+Wheel zooming is handled by the main window (anchored
        zoom needs scroll bar access); plain wheel scrolls normally."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            event.ignore()
            return
        super().wheelEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse movement for tooltips, drag, and rubber band."""
        if self._rubber_band.isVisible():
            self._rubber_band.setGeometry(
                QRect(self._rubber_origin, event.pos()).normalized()
            )
            return

        if (event.buttons() & Qt.MouseButton.LeftButton and
            self.drag_start_position is not None and
            self._press_on_activity and
            self.selected_activities):
            distance = (event.pos() - self.drag_start_position).manhattanLength()
            if distance >= DRAG_START_DISTANCE:
                self.start_drag()
                return

        for rect, activity in self.activity_rects:
            if rect.contains(event.pos()):
                self.setToolTip(self._create_tooltip(activity))
                return

        self.setToolTip("")

    def start_drag(self):
        """Start drag operation with selected activities"""
        if not self.selected_activities:
            return

        drag = QDrag(self)
        mime_data = QMimeData()

        activity_data = [
            {
                'timestamp': activity['timestamp'].isoformat(),
                'app_name': activity['app_name'],
                'duration': activity['duration'],
            }
            for activity in self.selected_activities
        ]

        mime_data.setText(json.dumps(activity_data))
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.CopyAction)

    def mousePressEvent(self, event):
        """Handle mouse clicks"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()
            self._press_on_activity = False

            for rect, activity in self.activity_rects:
                if rect.contains(event.pos()):
                    self._press_on_activity = True
                    self._handle_activity_click(activity, event.modifiers())
                    return

            # Empty space: start rubber band selection
            self._rubber_origin = event.pos()
            self._rubber_band.setGeometry(QRect(self._rubber_origin, QSize()))
            self._rubber_band.show()

        elif event.button() == Qt.MouseButton.RightButton:
            for rect, activity in self.activity_rects:
                if rect.contains(event.pos()):
                    self.show_context_menu(event.pos(), activity)
                    return

    def _handle_activity_click(self, activity, modifiers):
        """Update selection based on click modifiers."""
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            activities_list = [a for _, a in self.activity_rects]
            if (self.last_clicked_activity
                    and self.last_clicked_activity in activities_list):
                last_idx = activities_list.index(self.last_clicked_activity)
                current_idx = activities_list.index(activity)

                for idx in range(min(last_idx, current_idx),
                                 max(last_idx, current_idx) + 1):
                    if activities_list[idx] not in self.selected_activities:
                        self.selected_activities.append(activities_list[idx])
            elif activity not in self.selected_activities:
                self.selected_activities.append(activity)
        elif modifiers & Qt.KeyboardModifier.ControlModifier:
            if activity in self.selected_activities:
                self.selected_activities.remove(activity)
            else:
                self.selected_activities.append(activity)
        else:
            self.selected_activities = [activity]

        self.last_clicked_activity = activity
        self.update()

    def mouseReleaseEvent(self, event):
        """Finish rubber band selection."""
        if event.button() == Qt.MouseButton.LeftButton and self._rubber_band.isVisible():
            band_rect = self._rubber_band.geometry()
            self._rubber_band.hide()

            if band_rect.width() < 5 and band_rect.height() < 5:
                # Treat as a plain click on empty space: clear selection
                if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    self.selected_activities = []
                    self.last_clicked_activity = None
            else:
                additive = bool(
                    event.modifiers()
                    & (Qt.KeyboardModifier.ControlModifier
                       | Qt.KeyboardModifier.ShiftModifier)
                )
                if not additive:
                    self.selected_activities = []

                for rect, activity in self.activity_rects:
                    if rect.intersects(band_rect):
                        if activity not in self.selected_activities:
                            self.selected_activities.append(activity)

            self.update()

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Double click on empty space requests a manual entry."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        for rect, _activity in self.activity_rects:
            if rect.contains(event.pos()):
                return  # Double click on a block does nothing special

        clicked_dt = self._datetime_at_y(event.pos().y())
        self.manual_entry_requested.emit(clicked_dt)

    def _datetime_at_y(self, y: int) -> datetime:
        """Convert a vertical pixel position to a datetime (15 min steps)."""
        hours = (y - self.top_margin) / self.hour_height
        hours = min(max(hours, 0), 23.75)

        total_minutes = int(hours * 60 / 15) * 15  # round down to 15 min
        return datetime.combine(
            self.current_date, time(total_minutes // 60, total_minutes % 60)
        )

    # ------------------------------------------------------------------
    # Actions (assign / delete / select)
    # ------------------------------------------------------------------

    def show_context_menu(self, pos, activity):
        """Show context menu for activity"""
        menu = QMenu(self)

        projects = self.database.get_projects()

        activities_to_assign = (
            self.selected_activities if self.selected_activities else [activity]
        )
        is_multi = len(activities_to_assign) > 1

        if projects:
            if is_multi:
                menu.addSection(f"{len(activities_to_assign)} Aktivitäten zuordnen zu:")

            for project in projects:
                label = f"   {project['name']}" if is_multi else f"→ {project['name']}"
                action = QAction(label, self)
                action.triggered.connect(
                    lambda checked, acts=activities_to_assign, pid=project['id']:
                    self.assign_multiple_to_project(acts, pid)
                )
                menu.addAction(action)

            menu.addSeparator()

        if any(act.get('project_id') for act in activities_to_assign):
            clear_label = (
                "Projektzuordnungen entfernen" if is_multi
                else "Projektzuordnung entfernen"
            )
            clear_action = QAction(clear_label, self)
            clear_action.triggered.connect(
                lambda: self.assign_multiple_to_project(activities_to_assign, None)
            )
            menu.addAction(clear_action)

        menu.addSeparator()

        delete_label = (
            f"{len(activities_to_assign)} Aktivitäten löschen" if is_multi
            else "Aktivität löschen"
        )
        delete_action = QAction(delete_label, self)
        delete_action.triggered.connect(
            lambda: self.delete_activities(activities_to_assign)
        )
        menu.addAction(delete_action)

        menu.exec(self.mapToGlobal(pos))

    def _block_timerange(self, activity) -> tuple[datetime, datetime, str]:
        """Time range and app of a merged block for range operations."""
        start_time = activity['timestamp']
        end_time = activity.get(
            'end_time', start_time + timedelta(seconds=activity['duration'])
        )
        return start_time, end_time, activity['app_name']

    def assign_multiple_to_project(self, activities, project_id):
        """Assign merged blocks to a project (undoable)."""
        changes: list[tuple[int, Optional[int]]] = []
        total_count = 0

        for activity in activities:
            start_time, end_time, app_name = self._block_timerange(activity)

            affected = self.database.get_activities_in_timerange(
                start_time, end_time, app_name
            )
            changes.extend((a['id'], a.get('project_id')) for a in affected)

            total_count += self.database.assign_activities_by_timerange(
                start_time, end_time, app_name, project_id
            )

        logger.info(f"Assigned {total_count} activities to project")

        self.selected_activities = []
        self.undoable_action.emit({'type': 'assign', 'changes': changes})
        self.data_changed.emit()

    def delete_selected(self):
        """Delete the currently selected activities (Del shortcut)."""
        if self.selected_activities:
            self.delete_activities(list(self.selected_activities))

    def delete_activities(self, activities):
        """Delete activities with confirmation dialog (undoable)."""
        total_duration = sum(act['duration'] for act in activities)
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

        if len(activities) == 1:
            activity = activities[0]
            timestamp = activity['timestamp'].strftime('%H:%M:%S')
            message = (
                f"Möchtest du diese Aktivität wirklich löschen?\n\n"
                f"App: {activity['app_name']}\n"
                f"Zeit: {timestamp}\n"
                f"Dauer: {duration_str}"
            )
            title = "Aktivität löschen"
        else:
            message = (
                f"Möchtest du wirklich {len(activities)} Aktivitäten löschen?\n\n"
                f"Gesamtdauer: {duration_str}\n\n"
                f"Rückgängig mit Strg+Z möglich."
            )
            title = "Mehrere Aktivitäten löschen"

        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted_rows: list[dict] = []
        total_count = 0

        for activity in activities:
            start_time, end_time, app_name = self._block_timerange(activity)

            deleted_rows.extend(
                self.database.get_activities_in_timerange(
                    start_time, end_time, app_name
                )
            )
            total_count += self.database.delete_activities_by_timerange(
                start_time, end_time, app_name
            )

        logger.info(f"Deleted {total_count} activities")

        self.selected_activities = []
        self.undoable_action.emit({'type': 'delete', 'rows': deleted_rows})
        self.data_changed.emit()

    def select_all_visible(self):
        """Select every merged block currently shown (Ctrl+A)."""
        self.selected_activities = list(self.activities)
        self.update()

    def select_all_activities(self, activities):
        """Select all merged blocks that overlap the given activities."""
        self.selected_activities = []

        for target_activity in activities:
            target_start = target_activity['timestamp']
            target_end = target_start + timedelta(
                seconds=target_activity['duration']
            )

            for merged_activity in self.activities:
                merged_start = merged_activity['timestamp']
                merged_end = merged_activity.get(
                    'end_time',
                    merged_start + timedelta(seconds=merged_activity['duration']),
                )

                if (merged_activity['app_name'] == target_activity['app_name'] and
                        merged_start <= target_end and merged_end >= target_start):
                    if merged_activity not in self.selected_activities:
                        self.selected_activities.append(merged_activity)
                    break

        self.update()

    # ------------------------------------------------------------------
    # Tooltip
    # ------------------------------------------------------------------

    def _create_tooltip(self, activity):
        """Create tooltip text for activity"""
        timestamp = activity['timestamp']
        duration = activity['duration']
        end_time = timestamp + timedelta(seconds=duration)

        tooltip = f"<b>{activity['app_name']}</b><br>"

        window_title = activity.get('window_title', '')
        if window_title:
            tooltip += f"{window_title}<br>"

        tooltip += (
            f"<br><b>Zeit:</b> {timestamp.strftime('%H:%M:%S')}"
            f" - {end_time.strftime('%H:%M:%S')}<br>"
        )
        tooltip += f"<b>Dauer:</b> {self._format_duration(duration)}<br>"

        # Show real tracked time when merge gaps inflate the block
        tracked = activity.get('tracked_duration')
        if tracked is not None and tracked < duration:
            tooltip += (
                f"<b>Getrackt:</b> {self._format_duration(tracked)}"
                f" (Rest sind Lücken)<br>"
            )

        if activity.get('project_id'):
            project = self._cached_projects.get(activity['project_id'])
            if project:
                tooltip += f"<b>Projekt:</b> {project['name']}<br>"

        if activity.get('is_idle'):
            tooltip += "<i>(Idle)</i>"

        return tooltip

    @staticmethod
    def _format_duration(seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        if minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"
