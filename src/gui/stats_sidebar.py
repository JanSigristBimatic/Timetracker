"""Day statistics sidebar (time per project, app, and file)."""

from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.database_protocol import DatabaseProtocol
from utils.icon_cache import IconCache
from utils.window_title_parser import extract_filename_from_title

from .project_drop_widget import ProjectDropWidget

MAX_ROWS_PER_SECTION = 10
MIN_FILE_SECONDS = 60


class StatsSidebar(QFrame):
    """Sidebar showing aggregated statistics for the selected day.

    Signals:
        app_clicked: Emitted with the app name when an app row is clicked
        file_clicked: Emitted with the file name when a file row is clicked
        assignment_made: Emitted with an undo record after a drop assignment
    """

    app_clicked = pyqtSignal(str)
    file_clicked = pyqtSignal(str)
    assignment_made = pyqtSignal(dict)

    def __init__(self, database: DatabaseProtocol, icon_cache: IconCache):
        super().__init__()
        self.database = database
        self.icon_cache = icon_cache

        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        title = QLabel("Tagesstatistik")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        stats_scroll = QScrollArea()
        stats_scroll.setWidgetResizable(True)
        stats_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        stats_widget = QWidget()
        self.stats_layout = QVBoxLayout(stats_widget)
        self.stats_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        stats_scroll.setWidget(stats_widget)
        layout.addWidget(stats_scroll)

    def set_data(
        self,
        all_activities: list[dict[str, Any]],
        projects: list[dict[str, Any]],
    ) -> None:
        """Rebuild the statistics from the full (unfiltered) day data.

        Args:
            all_activities: All activities of the day, ignoring UI filters
            projects: All projects (id, name, color)
        """
        self._clear()

        active = [a for a in all_activities if not a.get("is_idle", False)]

        if not active:
            no_data = QLabel("Keine Daten für diesen Tag")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data.setProperty("class", "muted")
            self.stats_layout.addWidget(no_data)
            return

        total_seconds = sum(a["duration"] for a in active)
        project_map = {p["id"]: p for p in projects}

        self._build_project_section(active, project_map, total_seconds)
        self._build_app_section(active, total_seconds)
        self._build_file_section(active, total_seconds)

    def _clear(self) -> None:
        while self.stats_layout.count():
            child = self.stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _add_header(self, text: str, hint: Optional[str] = None) -> None:
        header = QLabel(text)
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setStyleSheet("margin-top: 12px; margin-bottom: 4px;")
        self.stats_layout.addWidget(header)

        if hint:
            hint_label = QLabel(hint)
            hint_font = QFont()
            hint_font.setPointSize(9)
            hint_font.setItalic(True)
            hint_label.setFont(hint_font)
            hint_label.setProperty("class", "muted")
            self.stats_layout.addWidget(hint_label)

    def _build_row_content(
        self,
        container: QWidget,
        name: str,
        seconds: int,
        total_seconds: int,
        icon_path: Optional[str] = None,
        color: Optional[str] = None,
        click_handler: Optional[Callable[[], None]] = None,
        bold_name: bool = False,
        italic_name: bool = False,
    ) -> None:
        """Fill a stat row (color chip / icon, name, time) into a container."""
        row_layout = QHBoxLayout(container)
        row_layout.setContentsMargins(5, 5, 5, 5)

        if color:
            color_label = QLabel()
            color_label.setFixedSize(18, 18)
            color_label.setStyleSheet(
                f"background-color: {color}; border-radius: 2px;"
            )
            color_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            row_layout.addWidget(color_label)
        elif icon_path:
            icon_pixmap = self.icon_cache.get_icon_pixmap(icon_path, size=32)
            if icon_pixmap and not icon_pixmap.isNull():
                scaled_icon = icon_pixmap.scaled(
                    24, 24,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                icon_label = QLabel()
                icon_label.setPixmap(scaled_icon)
                icon_label.setFixedSize(24, 24)
                icon_label.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents
                )
                row_layout.addWidget(icon_label)

        name_label = QLabel(name)
        name_font = QFont()
        name_font.setPointSize(11)
        name_font.setBold(bold_name)
        name_font.setItalic(italic_name)
        name_label.setFont(name_font)
        name_label.setTextFormat(Qt.TextFormat.PlainText)
        name_label.setWordWrap(False)

        if click_handler:
            name_label.setCursor(Qt.CursorShape.PointingHandCursor)
            name_label.mousePressEvent = lambda event: click_handler()
        else:
            name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        row_layout.addWidget(name_label, stretch=1)

        hours = seconds / 3600
        percentage = (seconds / total_seconds * 100) if total_seconds > 0 else 0
        time_label = QLabel(f"{hours:.1f}h ({percentage:.0f}%)")
        time_font = QFont()
        time_font.setPointSize(11)
        time_label.setFont(time_font)
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        time_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        time_label.setMinimumWidth(110)
        row_layout.addWidget(time_label)

    def _build_project_section(
        self,
        active: list[dict[str, Any]],
        project_map: dict[int, dict[str, Any]],
        total_seconds: int,
    ) -> None:
        self._add_header("Zeit pro Projekt", "Drag & Drop zum Zuordnen")

        project_times: dict[int, int] = {}
        unassigned_time = 0

        for activity in active:
            project_id = activity.get("project_id")
            if project_id is not None:
                project_times[project_id] = (
                    project_times.get(project_id, 0) + activity["duration"]
                )
            else:
                unassigned_time += activity["duration"]

        sorted_projects = sorted(
            project_times.items(), key=lambda x: x[1], reverse=True
        )

        for project_id, seconds in sorted_projects:
            project = project_map.get(project_id)
            if not project:
                continue

            row = ProjectDropWidget(
                self.database,
                project_id,
                project["name"],
                on_assigned=self.assignment_made.emit,
            )
            self._build_row_content(
                row,
                project["name"],
                seconds,
                total_seconds,
                color=project["color"],
                bold_name=True,
            )
            self.stats_layout.addWidget(row)

        if unassigned_time > 0:
            row = QWidget()
            self._build_row_content(
                row,
                "Ohne Projekt",
                unassigned_time,
                total_seconds,
                color="#95a5a6",
                italic_name=True,
            )
            self.stats_layout.addWidget(row)

    def _build_app_section(
        self, active: list[dict[str, Any]], total_seconds: int
    ) -> None:
        self._add_header("Zeit pro App", "Klick selektiert alle Aktivitäten")

        app_times: dict[str, int] = {}
        app_paths: dict[str, str] = {}

        for activity in active:
            app_name = activity["app_name"]
            app_times[app_name] = app_times.get(app_name, 0) + activity["duration"]
            if activity.get("process_path") and app_name not in app_paths:
                app_paths[app_name] = activity["process_path"]

        sorted_apps = sorted(app_times.items(), key=lambda x: x[1], reverse=True)

        for app_name, seconds in sorted_apps[:MAX_ROWS_PER_SECTION]:
            row = QWidget()
            self._build_row_content(
                row,
                app_name,
                seconds,
                total_seconds,
                icon_path=app_paths.get(app_name),
                click_handler=lambda app=app_name: self.app_clicked.emit(app),
            )
            self.stats_layout.addWidget(row)

        self._add_more_hint(len(sorted_apps) - MAX_ROWS_PER_SECTION, "Apps")

    def _build_file_section(
        self, active: list[dict[str, Any]], total_seconds: int
    ) -> None:
        self._add_header("Zeit pro Datei")

        file_times: dict[str, int] = {}
        file_app_paths: dict[str, str] = {}

        for activity in active:
            window_title = activity.get("window_title", "")
            if not window_title:
                continue

            filename = extract_filename_from_title(window_title)
            if not filename:
                continue

            if filename not in file_times:
                file_times[filename] = 0
                if activity.get("process_path"):
                    file_app_paths[filename] = activity["process_path"]
            file_times[filename] += activity["duration"]

        sorted_files = [
            (name, secs) for name, secs in
            sorted(file_times.items(), key=lambda x: x[1], reverse=True)
            if secs > MIN_FILE_SECONDS
        ]

        if not sorted_files:
            no_files = QLabel("Keine Dateien erkannt")
            no_files.setProperty("class", "muted")
            no_files.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stats_layout.addWidget(no_files)
            return

        for filename, seconds in sorted_files[:MAX_ROWS_PER_SECTION]:
            row = QWidget()
            self._build_row_content(
                row,
                filename,
                seconds,
                total_seconds,
                icon_path=file_app_paths.get(filename),
                click_handler=lambda file=filename: self.file_clicked.emit(file),
            )
            self.stats_layout.addWidget(row)

        self._add_more_hint(len(sorted_files) - MAX_ROWS_PER_SECTION, "Dateien")

    def _add_more_hint(self, remaining: int, label: str) -> None:
        if remaining > 0:
            more_label = QLabel(f"... und {remaining} weitere {label}")
            more_label.setProperty("class", "muted")
            more_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stats_layout.addWidget(more_label)
