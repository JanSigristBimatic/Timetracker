from datetime import datetime
import json

from PyQt6.QtCore import QDate, QEvent, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.database_protocol import DatabaseProtocol
from core.tracker import ActivityTracker
from utils.icon_cache import IconCache

from .export_dialog import ExportDialog
from .projects import ProjectManagerDialog
from .settings_dialog import SettingsDialog
from .timeline import TimelineWidget


class ProjectDropWidget(QWidget):
    """Widget that accepts drops for project assignment"""

    def __init__(self, project_id, project_name, main_window):
        super().__init__()
        self.project_id = project_id
        self.project_name = project_name
        self.main_window = main_window
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        """Accept drag events with activity data"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #e8f4f8; border-radius: 3px;")

    def dragLeaveEvent(self, event):
        """Reset style when drag leaves"""
        self.setStyleSheet("")

    def dropEvent(self, event):
        """Handle drop of activities"""
        self.setStyleSheet("")
        if event.mimeData().hasText():
            try:
                activity_data = json.loads(event.mimeData().text())
                # Assign all activities to this project
                total_count = 0
                for act_data in activity_data:
                    timestamp = datetime.fromisoformat(act_data['timestamp'])
                    duration = act_data['duration']
                    app_name = act_data['app_name']

                    # Use timerange assignment for merged activities
                    end_time = timestamp + datetime.timedelta(seconds=duration)
                    count = self.main_window.database.assign_activities_by_timerange(
                        timestamp, end_time, app_name, self.project_id
                    )
                    total_count += count

                print(f"Assigned {total_count} activities to project '{self.project_name}'")

                # Refresh timeline
                self.main_window.load_timeline()

                event.acceptProposedAction()
            except Exception as e:
                print(f"Error dropping activities: {e}")
                import traceback
                traceback.print_exc()


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self, database: DatabaseProtocol, tracker: ActivityTracker):
        super().__init__()
        self.database = database
        self.tracker = tracker
        self.current_date = datetime.now().date()

        # Icon cache
        self.icon_cache = IconCache()

        self.setup_ui()
        self.load_timeline()

        # Auto-refresh timeline every 30 seconds
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_timeline)
        self.refresh_timer.start(30000)

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("TimeTracker")
        self.setGeometry(100, 100, 1200, 700)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)

        # Top bar with date selector
        top_bar = self.create_top_bar()
        layout.addLayout(top_bar)

        # Main content area (timeline + stats sidebar)
        content_layout = QHBoxLayout()

        # Timeline widget
        self.timeline = TimelineWidget(self.database)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.timeline)
        self.scroll_area.setWidgetResizable(True)

        # Prevent scroll area from handling wheel events when Ctrl is pressed
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )

        # Install event filter to handle Ctrl+Wheel zoom
        self.scroll_area.installEventFilter(self)
        self.scroll_area.viewport().installEventFilter(self)

        content_layout.addWidget(self.scroll_area, stretch=3)

        # Day statistics sidebar
        self.stats_sidebar = self.create_stats_sidebar()
        content_layout.addWidget(self.stats_sidebar, stretch=1)

        layout.addLayout(content_layout)

        # Filter bar
        filter_bar = self.create_filter_bar()
        layout.addLayout(filter_bar)

        # Recent projects bar (between filters and stats)
        self.recent_projects_bar = self.create_recent_projects_bar()
        layout.addWidget(self.recent_projects_bar)

        # Bottom stats bar
        self.stats_label = QLabel()
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.stats_label)

    def create_top_bar(self):
        """Create top bar with controls"""
        layout = QHBoxLayout()

        # Date navigation
        prev_day_btn = QPushButton("◀ Vorheriger Tag")
        prev_day_btn.clicked.connect(self.previous_day)
        layout.addWidget(prev_day_btn)

        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.dateChanged.connect(self.date_changed)
        layout.addWidget(self.date_edit)

        next_day_btn = QPushButton("Nächster Tag ▶")
        next_day_btn.clicked.connect(self.next_day)
        layout.addWidget(next_day_btn)

        today_btn = QPushButton("Heute")
        today_btn.clicked.connect(self.go_to_today)
        layout.addWidget(today_btn)

        layout.addStretch()

        # Zoom controls
        zoom_label = QLabel("Zoom:")
        layout.addWidget(zoom_label)

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setMaximumWidth(30)
        zoom_out_btn.clicked.connect(self.zoom_out)
        layout.addWidget(zoom_out_btn)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(30)  # 30 pixels per hour
        self.zoom_slider.setMaximum(200)  # 200 pixels per hour
        self.zoom_slider.setValue(60)  # Default 60 pixels per hour
        self.zoom_slider.setMaximumWidth(150)
        self.zoom_slider.valueChanged.connect(self.zoom_changed)
        layout.addWidget(self.zoom_slider)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setMaximumWidth(30)
        zoom_in_btn.clicked.connect(self.zoom_in)
        layout.addWidget(zoom_in_btn)

        layout.addSpacing(20)

        # Project management button
        projects_btn = QPushButton("Projekte")
        projects_btn.clicked.connect(self.open_project_manager)
        layout.addWidget(projects_btn)

        # Export button
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self.open_export_dialog)
        layout.addWidget(export_btn)

        # Settings button
        settings_btn = QPushButton("Einstellungen")
        settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(settings_btn)

        # Refresh button
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.clicked.connect(self.refresh_timeline)
        layout.addWidget(refresh_btn)

        return layout

    def create_recent_projects_bar(self):
        """Create bar with recently used projects for quick assignment"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        frame.setStyleSheet("background-color: #f8f9fa; padding: 5px;")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 5, 10, 5)

        # Title
        title_label = QLabel("Zuletzt verwendet:")
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Container for project widgets
        self.recent_projects_container = QWidget()
        self.recent_projects_layout = QHBoxLayout(self.recent_projects_container)
        self.recent_projects_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_projects_layout.setSpacing(5)

        layout.addWidget(self.recent_projects_container)
        layout.addStretch()

        return frame

    def update_recent_projects_bar(self):
        """Update the recently used projects bar"""
        # Clear existing widgets
        while self.recent_projects_layout.count():
            child = self.recent_projects_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Get recently used projects
        recent_projects = self.database.get_recently_used_projects(limit=10)

        for project in recent_projects:
            # Create drop widget for each project
            project_widget = ProjectDropWidget(project['id'], project['name'], self)
            project_widget.setFixedHeight(30)
            project_widget.setStyleSheet(
                f"background-color: {project['color']}; "
                "border-radius: 5px; padding: 5px 10px; color: white; font-weight: bold;"
            )

            project_label = QLabel(project['name'])
            project_label.setStyleSheet("color: white; font-weight: bold;")
            project_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            project_layout = QHBoxLayout(project_widget)
            project_layout.setContentsMargins(5, 0, 5, 0)
            project_layout.addWidget(project_label)

            self.recent_projects_layout.addWidget(project_widget)

        # Add spacer if there are projects
        if recent_projects:
            self.recent_projects_layout.addStretch()

    def create_filter_bar(self):
        """Create filter bar"""
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Filter:"))

        # App filter
        layout.addWidget(QLabel("Programm:"))
        self.app_filter = QComboBox()
        self.app_filter.addItem("Alle", None)
        self.app_filter.currentIndexChanged.connect(self.apply_filters)
        layout.addWidget(self.app_filter)

        # Project filter
        layout.addWidget(QLabel("Projekt:"))
        self.project_filter = QComboBox()
        self.project_filter.addItem("Alle", None)
        self.project_filter.currentIndexChanged.connect(self.apply_filters)
        layout.addWidget(self.project_filter)

        # Clear filters button
        clear_btn = QPushButton("Filter zurücksetzen")
        clear_btn.clicked.connect(self.clear_filters)
        layout.addWidget(clear_btn)

        layout.addStretch()

        return layout

    def create_stats_sidebar(self):
        """Create statistics sidebar"""
        sidebar = QFrame()
        sidebar.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        sidebar.setMaximumWidth(450)
        sidebar.setMinimumWidth(400)

        layout = QVBoxLayout(sidebar)

        # Title
        title = QLabel("Tagesstatistik")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # Stats content (scrollable)
        stats_scroll = QScrollArea()
        stats_scroll.setWidgetResizable(True)
        stats_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        stats_widget = QWidget()
        self.stats_layout = QVBoxLayout(stats_widget)
        self.stats_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        stats_scroll.setWidget(stats_widget)
        layout.addWidget(stats_scroll)

        return sidebar

    def update_stats_sidebar(self, activities):
        """Update the statistics sidebar with project and app time"""
        # Clear existing widgets
        while self.stats_layout.count():
            child = self.stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not activities:
            no_data = QLabel("Keine Daten für diesen Tag")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data.setStyleSheet("color: #7f8c8d; padding: 20px;")
            self.stats_layout.addWidget(no_data)
            return

        # Get ALL activities for the day (not just filtered ones)
        start_datetime = datetime.combine(self.current_date, datetime.min.time())
        end_datetime = datetime.combine(self.current_date, datetime.max.time())
        all_activities = self.database.get_activities(
            start_date=start_datetime, end_date=end_datetime
        )

        # Calculate total time from all activities
        total_seconds = sum(
            a["duration"] for a in all_activities if not a.get("is_idle", False)
        )

        # --- Project Statistics ---
        project_header = QLabel("Zeit pro Projekt")
        project_header_font = QFont()
        project_header_font.setPointSize(12)
        project_header_font.setBold(True)
        project_header.setFont(project_header_font)
        project_header.setStyleSheet("margin-top: 10px; margin-bottom: 5px;")
        self.stats_layout.addWidget(project_header)

        # Group by project (use all activities, not filtered)
        project_times = {}
        unassigned_time = 0

        for activity in all_activities:
            if activity.get("is_idle", False):
                continue

            duration = activity["duration"]
            project_id = activity.get("project_id")

            if project_id:
                if project_id not in project_times:
                    project_times[project_id] = 0
                project_times[project_id] += duration
            else:
                unassigned_time += duration

        # Get project names and colors
        projects = self.database.get_projects()
        project_map = {p["id"]: p for p in projects}

        # Sort projects by time (descending)
        sorted_projects = sorted(
            project_times.items(), key=lambda x: x[1], reverse=True
        )

        # Display projects
        for project_id, seconds in sorted_projects:
            project = project_map.get(project_id)
            if not project:
                continue

            hours = seconds / 3600
            percentage = (seconds / total_seconds * 100) if total_seconds > 0 else 0

            # Project item (with drop support)
            project_widget = ProjectDropWidget(project_id, project["name"], self)
            project_layout = QHBoxLayout(project_widget)
            project_layout.setContentsMargins(5, 5, 5, 5)

            # Color indicator
            color_label = QLabel()
            color_label.setFixedSize(18, 18)
            color_label.setStyleSheet(
                f"background-color: {project['color']}; border-radius: 2px;"
            )
            project_layout.addWidget(color_label)

            # Project name
            name_label = QLabel(project["name"])
            name_font = QFont()
            name_font.setPointSize(11)
            name_font.setBold(True)
            name_label.setFont(name_font)
            project_layout.addWidget(name_label, stretch=1)

            # Time
            time_label = QLabel(f"{hours:.1f}h ({percentage:.0f}%)")
            time_font = QFont()
            time_font.setPointSize(11)
            time_label.setFont(time_font)
            time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            project_layout.addWidget(time_label)

            self.stats_layout.addWidget(project_widget)

        # Unassigned time
        if unassigned_time > 0:
            hours = unassigned_time / 3600
            percentage = (
                (unassigned_time / total_seconds * 100) if total_seconds > 0 else 0
            )

            unassigned_widget = QWidget()
            unassigned_layout = QHBoxLayout(unassigned_widget)
            unassigned_layout.setContentsMargins(5, 5, 5, 5)

            color_label = QLabel()
            color_label.setFixedSize(18, 18)
            color_label.setStyleSheet("background-color: #95a5a6; border-radius: 2px;")
            unassigned_layout.addWidget(color_label)

            name_label = QLabel("Ohne Projekt")
            name_font = QFont()
            name_font.setPointSize(11)
            name_font.setItalic(True)
            name_label.setFont(name_font)
            name_label.setStyleSheet("color: #7f8c8d;")
            unassigned_layout.addWidget(name_label, stretch=1)

            time_label = QLabel(f"{hours:.1f}h ({percentage:.0f}%)")
            time_font = QFont()
            time_font.setPointSize(11)
            time_label.setFont(time_font)
            time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            unassigned_layout.addWidget(time_label)

            self.stats_layout.addWidget(unassigned_widget)

        # --- App Statistics ---
        app_header = QLabel("Zeit pro App")
        app_header_font = QFont()
        app_header_font.setPointSize(12)
        app_header_font.setBold(True)
        app_header.setFont(app_header_font)
        app_header.setStyleSheet("margin-top: 15px; margin-bottom: 5px;")
        self.stats_layout.addWidget(app_header)

        # Group by app (use all activities, not filtered)
        app_times = {}
        for activity in all_activities:
            if activity.get("is_idle", False):
                continue

            app_name = activity["app_name"]
            duration = activity["duration"]

            if app_name not in app_times:
                app_times[app_name] = 0
            app_times[app_name] += duration

        # Sort apps by time (descending)
        sorted_apps = sorted(app_times.items(), key=lambda x: x[1], reverse=True)

        # Display top apps (limit to 10)
        # Build app -> process_path mapping
        app_paths = {}
        for activity in all_activities:
            if activity.get("process_path") and activity["app_name"] not in app_paths:
                app_paths[activity["app_name"]] = activity["process_path"]

        for app_name, seconds in sorted_apps[:10]:
            hours = seconds / 3600
            percentage = (seconds / total_seconds * 100) if total_seconds > 0 else 0

            app_widget = QWidget()
            app_layout = QHBoxLayout(app_widget)
            app_layout.setContentsMargins(5, 5, 5, 5)

            # Try to get app icon
            if app_name in app_paths:
                icon_pixmap = self.icon_cache.get_icon_pixmap(
                    app_paths[app_name], size=32
                )
                if icon_pixmap and not icon_pixmap.isNull():
                    # Scale icon to exact size
                    scaled_icon = icon_pixmap.scaled(
                        24,
                        24,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    icon_label = QLabel()
                    icon_label.setPixmap(scaled_icon)
                    icon_label.setFixedSize(24, 24)
                    app_layout.addWidget(icon_label)

            # App name (clickable)
            name_label = QLabel(app_name)
            name_font = QFont()
            name_font.setPointSize(11)
            name_label.setFont(name_font)
            name_label.setCursor(Qt.CursorShape.PointingHandCursor)
            name_label.mousePressEvent = lambda event, app=app_name: self.select_app_activities(app)
            app_layout.addWidget(name_label, stretch=1)

            # Time
            time_label = QLabel(f"{hours:.1f}h ({percentage:.0f}%)")
            time_font = QFont()
            time_font.setPointSize(11)
            time_label.setFont(time_font)
            time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            app_layout.addWidget(time_label)

            self.stats_layout.addWidget(app_widget)

        # Show "and X more" if there are more apps
        if len(sorted_apps) > 10:
            more_label = QLabel(f"... und {len(sorted_apps) - 10} weitere Apps")
            more_label.setStyleSheet(
                "color: #7f8c8d; font-style: italic; padding: 5px;"
            )
            more_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stats_layout.addWidget(more_label)

        # --- File Statistics ---
        file_header = QLabel("Zeit pro Datei")
        file_header_font = QFont()
        file_header_font.setPointSize(12)
        file_header_font.setBold(True)
        file_header.setFont(file_header_font)
        file_header.setStyleSheet("margin-top: 15px; margin-bottom: 5px;")
        self.stats_layout.addWidget(file_header)

        # Extract filenames from window titles and group by file
        file_times = {}
        file_app_paths = {}  # Store app path for each file to get icon
        for activity in all_activities:
            if activity.get("is_idle", False):
                continue

            window_title = activity.get("window_title", "")
            if not window_title:
                continue

            duration = activity["duration"]
            app_name = activity["app_name"]
            process_path = activity.get("process_path", "")

            # Try to extract filename from window title
            filename = self.extract_filename_from_title(window_title)
            if filename and filename != "Keine Datei erkannt":
                if filename not in file_times:
                    file_times[filename] = 0
                    if process_path:
                        file_app_paths[filename] = process_path
                file_times[filename] += duration

        # Sort files by time (descending)
        sorted_files = sorted(file_times.items(), key=lambda x: x[1], reverse=True)

        # Display top files (limit to 10, only show files with > 60 seconds)
        displayed_files = 0
        for filename, seconds in sorted_files:
            if seconds <= 60:  # Skip files with less than 1 minute
                continue
            if displayed_files >= 10:  # Limit to 10
                break

            hours = seconds / 3600
            percentage = (seconds / total_seconds * 100) if total_seconds > 0 else 0

            file_widget = QWidget()
            file_layout = QHBoxLayout(file_widget)
            file_layout.setContentsMargins(5, 5, 5, 5)

            # Try to get app icon
            if filename in file_app_paths:
                icon_pixmap = self.icon_cache.get_icon_pixmap(
                    file_app_paths[filename], size=32
                )
                if icon_pixmap and not icon_pixmap.isNull():
                    # Scale icon to exact size
                    scaled_icon = icon_pixmap.scaled(
                        24,
                        24,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    icon_label = QLabel()
                    icon_label.setPixmap(scaled_icon)
                    icon_label.setFixedSize(24, 24)
                    file_layout.addWidget(icon_label)

            # File name (clickable)
            name_label = QLabel(filename)
            name_font = QFont()
            name_font.setPointSize(11)
            name_label.setFont(name_font)
            name_label.setCursor(Qt.CursorShape.PointingHandCursor)
            name_label.mousePressEvent = lambda event, file=filename: self.select_file_activities(file)
            file_layout.addWidget(name_label, stretch=1)

            # Time
            time_label = QLabel(f"{hours:.1f}h ({percentage:.0f}%)")
            time_font = QFont()
            time_font.setPointSize(11)
            time_label.setFont(time_font)
            time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            file_layout.addWidget(time_label)

            self.stats_layout.addWidget(file_widget)
            displayed_files += 1

        # Show "and X more" if there are more files
        remaining_files = len([f for f in sorted_files if f[1] > 60]) - displayed_files
        if remaining_files > 0:
            more_label = QLabel(f"... und {remaining_files} weitere Dateien")
            more_label.setStyleSheet(
                "color: #7f8c8d; font-style: italic; padding: 5px;"
            )
            more_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stats_layout.addWidget(more_label)

        # Show message if no files detected
        if displayed_files == 0:
            no_files_label = QLabel("Keine Dateien erkannt")
            no_files_label.setStyleSheet(
                "color: #7f8c8d; font-style: italic; padding: 5px;"
            )
            no_files_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stats_layout.addWidget(no_files_label)

    def extract_filename_from_title(self, window_title):
        """Extract filename or relevant content from window title"""
        import re

        if not window_title:
            return None

        # Pattern 1: Autodesk/CAD style - "Program - [filename.ext]" or "Program [filename.ext]"
        autodesk_match = re.search(r"\[([^\]]+\.[a-zA-Z0-9]+)\]", window_title)
        if autodesk_match:
            return autodesk_match.group(1)

        # Pattern 1b: Cyclone 3DR - "project_name - Cyclone 3DR version"
        cyclone_match = re.match(r"^(.+?)\s*-\s*Cyclone 3DR", window_title)
        if cyclone_match:
            return cyclone_match.group(1).strip()

        # Pattern 1c: Revit - "project_name - Autodesk Revit" or similar
        revit_match = re.match(r"^(.+?)\s*-\s*(Autodesk\s+)?Revit", window_title)
        if revit_match:
            return revit_match.group(1).strip()

        # Pattern 1d: Blender - "filename.blend - Blender" or "Blender - filename.blend"
        blender_match = re.search(r"(.+?\.blend)", window_title)
        if blender_match and "Blender" in window_title:
            return blender_match.group(1).strip()

        # Pattern 2: Teams chat - "Chat | Person Name | ..."
        teams_match = re.search(r"Chat\s*\|\s*([^|]+?)\s*\|", window_title)
        if teams_match:
            return teams_match.group(1).strip()

        # Pattern 3: Slack - "#channel-name | Workspace - Slack"
        slack_match = re.search(r"^(#[^\|]+)\s*\|", window_title)
        if slack_match:
            return slack_match.group(1).strip()

        # Pattern 4: Zoom - "Zoom Meeting - Meeting Name" or "Zoom Meeting"
        zoom_match = re.match(r"^Zoom Meeting\s*-\s*(.+)", window_title)
        if zoom_match:
            return zoom_match.group(1).strip()

        # Pattern 5: JetBrains IDEs - "filename.ext - Project [Path] - IDE"
        jetbrains_match = re.match(
            r"^([^\-]+\.[a-zA-Z0-9]+)\s*-\s*([^\[]+)", window_title
        )
        if jetbrains_match and (
            "PyCharm" in window_title
            or "IntelliJ" in window_title
            or "WebStorm" in window_title
            or "PhpStorm" in window_title
        ):
            filename = jetbrains_match.group(1).strip()
            project = jetbrains_match.group(2).strip()
            return f"{filename} - {project}"

        # Pattern 6: VS Code style - "content... - Project - Visual Studio Code"
        vscode_match = re.match(
            r"^(.+?)\s*-\s*([^-]+)\s*-\s*Visual Studio Code", window_title
        )
        if vscode_match:
            content = vscode_match.group(1).strip()
            project = vscode_match.group(2).strip()
            return f"{content} - {project}"

        # Pattern 7: Microsoft Office - "filename.ext - Word/Excel/PowerPoint"
        office_match = re.match(
            r"^(.+?\.(docx?|xlsx?|pptx?|pdf))\s*-\s*(Microsoft\s+)?(Word|Excel|PowerPoint|Outlook)",
            window_title,
            re.IGNORECASE,
        )
        if office_match:
            return office_match.group(1)

        # Pattern 8: Adobe Reader/Acrobat - "filename.pdf - Adobe..."
        adobe_match = re.match(r"^(.+?\.pdf)\s*-\s*Adobe", window_title, re.IGNORECASE)
        if adobe_match:
            return adobe_match.group(1)

        # Pattern 9: Notepad++ - "filename.ext - Notepad++"
        notepad_match = re.match(
            r"^(.+?\.[a-zA-Z0-9]+)\s*-\s*Notepad\+\+", window_title
        )
        if notepad_match:
            return notepad_match.group(1)

        # Pattern 10: Browsers - "Page Title - Browser Name"
        browser_match = re.match(
            r"^(.+?)\s*-\s*(Google Chrome|Mozilla Firefox|Microsoft Edge|Opera|Safari|Brave)$",
            window_title,
        )
        if browser_match:
            page_title = browser_match.group(1).strip()
            # Limit very long page titles
            return page_title[:80] if len(page_title) > 80 else page_title

        # Pattern 11: Outlook - various formats
        if "Outlook" in window_title:
            # Remove " - Outlook" suffix
            outlook_cleaned = re.sub(
                r"\s*-\s*(Microsoft\s+)?Outlook.*$", "", window_title
            )
            if outlook_cleaned:
                # For inbox view, take first part
                parts = outlook_cleaned.split(" - ")
                return parts[0].strip()[:60]

        # Pattern 12: Figma - "Design Name - Figma"
        figma_match = re.match(r"^(.+?)\s*-\s*Figma$", window_title)
        if figma_match:
            return figma_match.group(1).strip()

        # Pattern 13: General file with extension
        file_match = re.search(r'([^\\/:\*\?"<>\|]+\.[a-zA-Z0-9]+)', window_title)
        if file_match:
            filename = file_match.group(1)
            # Remove common application suffixes
            filename = re.sub(
                r"\s*-\s*(Visual Studio Code|Notepad|Word|Excel|PowerPoint|Adobe|Reader).*$",
                "",
                filename,
            )
            return filename.strip()

        # Pattern 14: For other apps, extract first meaningful part
        # Remove common app names at the end
        cleaned = re.sub(
            r"\s*-\s*(Microsoft Teams|Google Chrome|Firefox|Edge|Outlook|Discord|Spotify)$",
            "",
            window_title,
        )

        # If we removed something and there's still content, return it
        if cleaned != window_title and cleaned.strip():
            # Limit length and take first part if multiple separators
            parts = cleaned.split(" - ")
            if len(parts) > 0:
                result = parts[0].strip()
                return result[:60] if len(result) > 60 else result

        return None

    def previous_day(self):
        """Go to previous day"""
        current = self.date_edit.date()
        self.date_edit.setDate(current.addDays(-1))

    def next_day(self):
        """Go to next day"""
        current = self.date_edit.date()
        self.date_edit.setDate(current.addDays(1))

    def go_to_today(self):
        """Go to today"""
        self.date_edit.setDate(QDate.currentDate())

    def date_changed(self, qdate):
        """Handle date change"""
        self.current_date = qdate.toPyDate()
        self.load_timeline()

    def load_timeline(self):
        """Load timeline for current date"""
        start_datetime = datetime.combine(self.current_date, datetime.min.time())
        end_datetime = datetime.combine(self.current_date, datetime.max.time())

        # Get selected filters
        selected_project = self.project_filter.currentData()

        # Handle "Ohne Projekt" filter
        if selected_project == "NO_PROJECT":
            activities = self.database.get_activities(
                start_date=start_datetime,
                end_date=end_datetime,
            )
            # Filter to only activities without project
            activities = [a for a in activities if a.get("project_id") is None]
        else:
            activities = self.database.get_activities(
                start_date=start_datetime,
                end_date=end_datetime,
                project_id=selected_project,
            )

        # Apply app filter
        selected_app = self.app_filter.currentData()
        if selected_app:
            activities = [a for a in activities if a["app_name"] == selected_app]

        self.timeline.set_activities(activities, self.current_date)
        self.update_stats(activities)
        self.update_stats_sidebar(activities)
        self.update_filter_options()
        self.update_recent_projects_bar()

    def refresh_timeline(self):
        """Refresh the timeline"""
        self.load_timeline()

    def update_stats(self, activities):
        """Update statistics display"""
        # Get ALL activities for the day for correct total time
        start_datetime = datetime.combine(self.current_date, datetime.min.time())
        end_datetime = datetime.combine(self.current_date, datetime.max.time())
        all_activities = self.database.get_activities(
            start_date=start_datetime, end_date=end_datetime
        )

        if not all_activities:
            self.stats_label.setText("Keine Aktivitäten für diesen Tag")
            return

        # Calculate total from all activities
        total_seconds = sum(activity["duration"] for activity in all_activities)
        active_seconds = sum(
            activity["duration"]
            for activity in all_activities
            if not activity.get("is_idle", False)
        )

        total_hours = total_seconds / 3600
        active_hours = active_seconds / 3600
        idle_hours = (total_seconds - active_seconds) / 3600

        # Show filtered count if filter is active
        filter_info = ""
        if len(activities) < len(all_activities):
            filter_info = f" (Filter: {len(activities)} Aktivitäten)"

        stats_text = (
            f"Gesamt: {total_hours:.1f}h | "
            f"Aktiv: {active_hours:.1f}h | "
            f"Idle: {idle_hours:.1f}h | "
            f"Aktivitäten: {len(all_activities)}{filter_info}"
        )

        self.stats_label.setText(stats_text)

    def zoom_in(self):
        """Zoom in (increase hour height)"""
        current = self.zoom_slider.value()
        self.zoom_slider.setValue(min(current + 10, 200))

    def zoom_out(self):
        """Zoom out (decrease hour height)"""
        current = self.zoom_slider.value()
        self.zoom_slider.setValue(max(current - 10, 30))

    def zoom_changed(self, value):
        """Handle zoom slider change"""
        self.timeline.set_zoom(value)
        self.timeline.update()

    def open_project_manager(self):
        """Open project management dialog"""
        dialog = ProjectManagerDialog(self.database, self)
        if dialog.exec():
            # Reload timeline to show updated project colors
            self.load_timeline()

    def open_export_dialog(self):
        """Open export dialog"""
        dialog = ExportDialog(self.database, self)
        dialog.exec()

    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self)
        dialog.exec()

    def eventFilter(self, obj, event):
        """Filter events to handle Ctrl+Wheel zoom without scrolling"""
        if event.type() == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                # Ctrl+Wheel: Zoom without scrolling
                # Forward to timeline widget for zoom handling
                self.timeline.wheelEvent(event)
                event.accept()
                return True  # Event handled, block scrolling completely
        return super().eventFilter(obj, event)

    def update_filter_options(self):
        """Update filter dropdown options based on current date"""
        start_datetime = datetime.combine(self.current_date, datetime.min.time())
        end_datetime = datetime.combine(self.current_date, datetime.max.time())

        # Get all activities for this date
        all_activities = self.database.get_activities(
            start_date=start_datetime, end_date=end_datetime
        )

        # Get unique apps
        apps = sorted(set(a["app_name"] for a in all_activities))
        current_app = self.app_filter.currentData()

        self.app_filter.blockSignals(True)
        self.app_filter.clear()
        self.app_filter.addItem("Alle", None)
        for app in apps:
            self.app_filter.addItem(app, app)

        # Restore selection if still valid
        if current_app:
            index = self.app_filter.findData(current_app)
            if index >= 0:
                self.app_filter.setCurrentIndex(index)

        self.app_filter.blockSignals(False)

        # Get all projects
        projects = self.database.get_projects()
        current_project = self.project_filter.currentData()

        self.project_filter.blockSignals(True)
        self.project_filter.clear()
        self.project_filter.addItem("Alle", None)
        self.project_filter.addItem("Ohne Projekt", "NO_PROJECT")
        for project in projects:
            self.project_filter.addItem(project["name"], project["id"])

        # Restore selection if still valid
        if current_project:
            index = self.project_filter.findData(current_project)
            if index >= 0:
                self.project_filter.setCurrentIndex(index)

        self.project_filter.blockSignals(False)

    def apply_filters(self):
        """Apply selected filters"""
        self.load_timeline()

    def clear_filters(self):
        """Clear all filters"""
        self.app_filter.setCurrentIndex(0)
        self.project_filter.setCurrentIndex(0)

    def select_app_activities(self, app_name):
        """Select all activities for a specific app"""
        # Filter by app if not already filtered
        app_index = self.app_filter.findData(app_name)
        if app_index >= 0:
            self.app_filter.setCurrentIndex(app_index)

        # Get all activities matching the current filter (which now includes the app)
        start_datetime = datetime.combine(self.current_date, datetime.min.time())
        end_datetime = datetime.combine(self.current_date, datetime.max.time())

        selected_project = self.project_filter.currentData()

        # Handle "Ohne Projekt" filter
        if selected_project == "NO_PROJECT":
            activities = self.database.get_activities(
                start_date=start_datetime,
                end_date=end_datetime,
            )
            activities = [a for a in activities if a.get("project_id") is None and a["app_name"] == app_name]
        else:
            activities = self.database.get_activities(
                start_date=start_datetime,
                end_date=end_datetime,
                project_id=selected_project,
            )
            activities = [a for a in activities if a["app_name"] == app_name]

        # Select all activities in timeline
        self.timeline.select_all_activities(activities)

    def select_file_activities(self, filename):
        """Select all activities for a specific file"""
        # Get all activities for the day
        start_datetime = datetime.combine(self.current_date, datetime.min.time())
        end_datetime = datetime.combine(self.current_date, datetime.max.time())

        selected_project = self.project_filter.currentData()

        # Handle "Ohne Projekt" filter
        if selected_project == "NO_PROJECT":
            activities = self.database.get_activities(
                start_date=start_datetime,
                end_date=end_datetime,
            )
            activities = [a for a in activities if a.get("project_id") is None]
        else:
            activities = self.database.get_activities(
                start_date=start_datetime,
                end_date=end_datetime,
                project_id=selected_project,
            )

        # Apply app filter if active
        selected_app = self.app_filter.currentData()
        if selected_app:
            activities = [a for a in activities if a["app_name"] == selected_app]

        # Filter by filename extracted from window title
        matching_activities = []
        for activity in activities:
            window_title = activity.get("window_title", "")
            if window_title:
                extracted_filename = self.extract_filename_from_title(window_title)
                if extracted_filename == filename:
                    matching_activities.append(activity)

        # Select all matching activities in timeline
        self.timeline.select_all_activities(matching_activities)
