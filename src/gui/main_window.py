import logging
from datetime import date, datetime, timedelta
from typing import Optional

from PyQt6.QtCore import QDate, QEvent, QSettings, Qt, QTimer
from PyQt6.QtGui import QCursor, QFont, QFontMetrics, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.database_protocol import DatabaseProtocol
from core.tracker import ActivityTracker
from utils.config import get_env_int
from utils.icon_cache import IconCache
from utils.window_title_parser import extract_filename_from_title

from .assignment_suggestions import AssignmentSuggestionsDialog
from .calendar_import_dialog import CalendarImportDialog
from .dashboard_view import DashboardView
from .export_dialog import ExportDialog
from .manual_entry_dialog import ManualEntryDialog
from .period_views import MonthView, WeekView
from .project_drop_widget import ProjectDropWidget
from .projects import ProjectManagerDialog
from .rules_dialog import RulesDialog
from .settings_dialog import SettingsDialog
from .stats_sidebar import StatsSidebar
from .timeline import TimelineWidget

logger = logging.getLogger(__name__)

VIEW_DAY = 0
VIEW_WEEK = 1
VIEW_MONTH = 2
VIEW_DASHBOARD = 3

MAX_UNDO_STEPS = 20
ZOOM_MIN = 30
ZOOM_MAX = 200


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self, database: DatabaseProtocol, tracker: ActivityTracker):
        super().__init__()
        self.database = database
        self.tracker = tracker
        self.current_date = datetime.now().date()

        self.icon_cache = IconCache()
        self.undo_stack: list[dict] = []
        self._day_activities: list[dict] = []
        self._auto_scrolled_date = None

        self.setup_ui()
        self.setup_shortcuts()
        self.restore_window_state()
        self.load_current_view()

        # Auto-refresh (day view of today only; selection is preserved)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh)
        self.refresh_timer.start(30000)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("TimeTracker")
        self.setGeometry(100, 100, 1200, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        layout.addLayout(self.create_top_bar())

        # Stacked views: day (timeline + sidebar), week, month
        self.view_stack = QStackedWidget()

        self.timeline = TimelineWidget(self.database)
        self.timeline.data_changed.connect(self.load_current_view)
        self.timeline.undoable_action.connect(self.push_undo)
        self.timeline.manual_entry_requested.connect(self.open_manual_entry)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.timeline)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.scroll_area.installEventFilter(self)
        self.scroll_area.viewport().installEventFilter(self)

        self.stats_sidebar = StatsSidebar(self.database, self.icon_cache)
        self.stats_sidebar.app_clicked.connect(self.select_app_activities)
        self.stats_sidebar.file_clicked.connect(self.select_file_activities)
        self.stats_sidebar.assignment_made.connect(self.on_drop_assignment)

        self.day_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.day_splitter.addWidget(self.scroll_area)
        self.day_splitter.addWidget(self.stats_sidebar)
        self.day_splitter.setStretchFactor(0, 3)
        self.day_splitter.setStretchFactor(1, 1)
        self.day_splitter.setSizes([750, 420])
        self.view_stack.addWidget(self.day_splitter)

        self.week_view = WeekView()
        self.week_view.day_clicked.connect(self.jump_to_day)
        self.view_stack.addWidget(self.week_view)

        self.month_view = MonthView()
        self.month_view.day_clicked.connect(self.jump_to_day)
        self.view_stack.addWidget(self.month_view)

        self.dashboard_view = DashboardView(self.database)
        self.view_stack.addWidget(self.dashboard_view)

        layout.addWidget(self.view_stack, stretch=1)

        # Filter bar (day view only)
        self.filter_bar = self.create_filter_bar()
        layout.addWidget(self.filter_bar)

        # Recent projects bar (day view only)
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
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setMaximumWidth(36)
        self.prev_btn.setToolTip("Vorheriger Zeitraum (Alt+Links)")
        self.prev_btn.clicked.connect(self.previous_period)
        layout.addWidget(self.prev_btn)

        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.dateChanged.connect(self.date_changed)
        layout.addWidget(self.date_edit)

        self.next_btn = QPushButton("▶")
        self.next_btn.setMaximumWidth(36)
        self.next_btn.setToolTip("Nächster Zeitraum (Alt+Rechts)")
        self.next_btn.clicked.connect(self.next_period)
        layout.addWidget(self.next_btn)

        self.today_btn = QPushButton("Heute")
        self.today_btn.setToolTip("Zum heutigen Tag (Strg+T)")
        self.today_btn.clicked.connect(self.go_to_today)
        layout.addWidget(self.today_btn)

        layout.addSpacing(12)

        # View switcher
        self.view_group = QButtonGroup(self)
        for index, label, tip in (
            (VIEW_DAY, "Tag", "Tagesansicht (Strg+1)"),
            (VIEW_WEEK, "Woche", "Wochenansicht (Strg+2)"),
            (VIEW_MONTH, "Monat", "Monatsansicht (Strg+3)"),
            (VIEW_DASHBOARD, "Auswertung", "Projekt-Auswertung (Strg+4)"),
        ):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            if index == VIEW_DAY:
                btn.setChecked(True)
            self.view_group.addButton(btn, index)
            layout.addWidget(btn)
        self.view_group.idClicked.connect(self.switch_view)

        layout.addStretch()

        # Zoom controls (day view only)
        self.zoom_widget = QWidget()
        zoom_layout = QHBoxLayout(self.zoom_widget)
        zoom_layout.setContentsMargins(0, 0, 0, 0)

        zoom_layout.addWidget(QLabel("Zoom:"))

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setMaximumWidth(30)
        zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_layout.addWidget(zoom_out_btn)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(ZOOM_MIN)
        self.zoom_slider.setMaximum(ZOOM_MAX)
        self.zoom_slider.setValue(60)
        self.zoom_slider.setMaximumWidth(150)
        self.zoom_slider.valueChanged.connect(self.zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setMaximumWidth(30)
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(zoom_in_btn)

        layout.addWidget(self.zoom_widget)
        layout.addSpacing(12)

        # Action buttons
        entry_btn = QPushButton("+ Eintrag")
        entry_btn.setToolTip(
            "Manuellen Eintrag hinzufügen (Strg+N oder Doppelklick in Timeline)"
        )
        entry_btn.clicked.connect(lambda: self.open_manual_entry())
        layout.addWidget(entry_btn)

        projects_btn = QPushButton("Projekte")
        projects_btn.clicked.connect(self.open_project_manager)
        layout.addWidget(projects_btn)

        rules_btn = QPushButton("Regeln")
        rules_btn.setToolTip("Automatische Zuordnungsregeln verwalten")
        rules_btn.clicked.connect(self.open_rules_dialog)
        layout.addWidget(rules_btn)

        suggestions_btn = QPushButton("Vorschläge")
        suggestions_btn.setToolTip(
            "Projektvorschläge aus bisherigen Zuordnungen prüfen und übernehmen"
        )
        suggestions_btn.clicked.connect(self.open_assignment_suggestions)
        suggestions_btn.setProperty("class", "primary")
        layout.addWidget(suggestions_btn)

        import_btn = QPushButton("Import")
        import_btn.setToolTip("Kalender-Termine aus ICS-Datei importieren")
        import_btn.clicked.connect(self.open_calendar_import)
        layout.addWidget(import_btn)

        export_btn = QPushButton("Export")
        export_btn.setToolTip("Daten exportieren (Strg+E)")
        export_btn.clicked.connect(self.open_export_dialog)
        layout.addWidget(export_btn)

        settings_btn = QPushButton("Einstellungen")
        settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(settings_btn)

        return layout

    def create_filter_bar(self) -> QWidget:
        """Create filter bar"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Filter:"))

        layout.addWidget(QLabel("Programm:"))
        self.app_filter = QComboBox()
        self.app_filter.addItem("Alle", None)
        self.app_filter.currentIndexChanged.connect(self.apply_filters)
        layout.addWidget(self.app_filter)

        layout.addWidget(QLabel("Projekt:"))
        self.project_filter = QComboBox()
        self.project_filter.addItem("Alle", None)
        self.project_filter.currentIndexChanged.connect(self.apply_filters)
        layout.addWidget(self.project_filter)

        clear_btn = QPushButton("Filter zurücksetzen")
        clear_btn.clicked.connect(self.clear_filters)
        layout.addWidget(clear_btn)

        layout.addStretch()

        return widget

    def create_recent_projects_bar(self):
        """Create bar with recently used projects for quick assignment"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        frame.setProperty("class", "card")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 5, 10, 5)

        title_label = QLabel("Zuletzt verwendet:")
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        desc_label = QLabel("(Aktivitäten per Drag & Drop hier zuordnen)")
        desc_font = QFont()
        desc_font.setPointSize(9)
        desc_font.setItalic(True)
        desc_label.setFont(desc_font)
        desc_label.setProperty("class", "muted")
        layout.addWidget(desc_label)

        self.recent_projects_container = QWidget()
        self.recent_projects_layout = QHBoxLayout(self.recent_projects_container)
        self.recent_projects_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_projects_layout.setSpacing(5)

        layout.addWidget(self.recent_projects_container)
        layout.addStretch()

        return frame

    def _delete_selected_in_day_view(self):
        """Delete key only acts where the selection is visible"""
        if self.current_view() == VIEW_DAY:
            self.timeline.delete_selected()

    def setup_shortcuts(self):
        """Register keyboard shortcuts"""
        QShortcut(QKeySequence("Alt+Left"), self, self.previous_period)
        QShortcut(QKeySequence("Alt+Right"), self, self.next_period)
        QShortcut(QKeySequence("Ctrl+T"), self, self.go_to_today)
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo_last_action)
        QShortcut(QKeySequence("Delete"), self, self._delete_selected_in_day_view)
        QShortcut(QKeySequence("Ctrl+A"), self, self.timeline.select_all_visible)
        QShortcut(QKeySequence("Ctrl+E"), self, self.open_export_dialog)
        QShortcut(QKeySequence("Ctrl+N"), self, lambda: self.open_manual_entry())
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self.set_view(VIEW_DAY))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self.set_view(VIEW_WEEK))
        QShortcut(QKeySequence("Ctrl+3"), self, lambda: self.set_view(VIEW_MONTH))
        QShortcut(QKeySequence("Ctrl+4"), self, lambda: self.set_view(VIEW_DASHBOARD))
        QShortcut(QKeySequence("F5"), self, self.load_current_view)

    # ------------------------------------------------------------------
    # Window state persistence
    # ------------------------------------------------------------------

    def restore_window_state(self):
        """Restore window geometry and splitter position"""
        settings = QSettings("TimeTracker", "TimeTracker")

        geometry = settings.value("mainwindow/geometry")
        if geometry:
            self.restoreGeometry(geometry)

        splitter_state = settings.value("mainwindow/splitter")
        if splitter_state:
            self.day_splitter.restoreState(splitter_state)

        zoom = settings.value("mainwindow/zoom")
        if zoom:
            self.zoom_slider.setValue(int(zoom))

    def save_window_state(self):
        """Persist window geometry and splitter position"""
        settings = QSettings("TimeTracker", "TimeTracker")
        settings.setValue("mainwindow/geometry", self.saveGeometry())
        settings.setValue("mainwindow/splitter", self.day_splitter.saveState())
        settings.setValue("mainwindow/zoom", self.zoom_slider.value())

    def closeEvent(self, event):
        """Save state when the window is closed (app keeps running in tray)"""
        self.save_window_state()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Navigation & views
    # ------------------------------------------------------------------

    def current_view(self) -> int:
        return self.view_stack.currentIndex()

    def set_view(self, index: int):
        """Switch view programmatically (shortcut helper)"""
        button = self.view_group.button(index)
        if button:
            button.setChecked(True)
        self.switch_view(index)

    def switch_view(self, index: int):
        """Switch between day, week, month, and dashboard view"""
        self.view_stack.setCurrentIndex(index)

        is_day = index == VIEW_DAY
        self.zoom_widget.setVisible(is_day)
        self.filter_bar.setVisible(is_day)
        self.recent_projects_bar.setVisible(is_day)

        # The dashboard has its own period selector
        has_date_nav = index != VIEW_DASHBOARD
        self.prev_btn.setVisible(has_date_nav)
        self.date_edit.setVisible(has_date_nav)
        self.next_btn.setVisible(has_date_nav)
        self.today_btn.setVisible(has_date_nav)

        self.load_current_view()

    def jump_to_day(self, day: date):
        """Switch to day view for the given date (from week/month view)"""
        self.set_view(VIEW_DAY)
        self.date_edit.setDate(QDate(day.year, day.month, day.day))

    def previous_period(self):
        """Go one day/week/month back depending on the active view"""
        self._shift_date(-1)

    def next_period(self):
        """Go one day/week/month forward depending on the active view"""
        self._shift_date(1)

    def _shift_date(self, direction: int):
        current = self.date_edit.date()
        view = self.current_view()

        if view == VIEW_DASHBOARD:
            return  # Dashboard uses its own period selector
        if view == VIEW_WEEK:
            self.date_edit.setDate(current.addDays(7 * direction))
        elif view == VIEW_MONTH:
            self.date_edit.setDate(current.addMonths(direction))
        else:
            self.date_edit.setDate(current.addDays(direction))

    def go_to_today(self):
        """Go to today"""
        self.date_edit.setDate(QDate.currentDate())

    def date_changed(self, qdate):
        """Handle date change"""
        self.current_date = qdate.toPyDate()
        self.load_current_view()

    def auto_refresh(self):
        """Periodic refresh; only the live day view needs it"""
        if self.current_view() == VIEW_DAY and self.current_date == date.today():
            self.load_current_view()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_current_view(self):
        """Reload data for the active view"""
        view = self.current_view()
        if view == VIEW_WEEK:
            self.load_week_view()
        elif view == VIEW_MONTH:
            self.load_month_view()
        elif view == VIEW_DASHBOARD:
            self.dashboard_view.refresh()
            self.stats_label.setText("")
        else:
            self.load_day_view()

    def _load_range(self, start_day: date, end_day: date) -> list[dict]:
        """Load activities for an inclusive day range (single query)."""
        start_dt = datetime.combine(start_day, datetime.min.time())
        end_dt = datetime.combine(end_day, datetime.max.time())
        return self.database.get_activities(start_date=start_dt, end_date=end_dt)

    def load_day_view(self):
        """Load timeline for the current date (one DB query for all parts)"""
        all_activities = self._load_range(self.current_date, self.current_date)
        self._day_activities = all_activities
        projects = self.database.get_projects()

        filtered = self._apply_activity_filters(all_activities)

        self.timeline.set_activities(filtered, self.current_date)
        self.stats_sidebar.set_data(all_activities, projects)
        self.update_stats(all_activities, len(filtered))
        self.update_filter_options(all_activities, projects)
        self.update_recent_projects_bar()
        self._auto_scroll_to_now()

    def _apply_activity_filters(self, activities: list[dict]) -> list[dict]:
        """Apply app/project filter selection to the day's activities"""
        selected_project = self.project_filter.currentData()
        if selected_project == "NO_PROJECT":
            activities = [a for a in activities if a.get("project_id") is None]
        elif selected_project is not None:
            activities = [
                a for a in activities if a.get("project_id") == selected_project
            ]

        selected_app = self.app_filter.currentData()
        if selected_app:
            activities = [a for a in activities if a["app_name"] == selected_app]

        return activities

    def _auto_scroll_to_now(self):
        """Scroll the day view to the current time (once per day switch)"""
        if self.current_date != date.today():
            return
        if self._auto_scrolled_date == self.current_date:
            return

        self._auto_scrolled_date = self.current_date

        def scroll():
            y = self.timeline.now_line_y()
            if y is not None:
                viewport_height = self.scroll_area.viewport().height()
                self.scroll_area.verticalScrollBar().setValue(
                    max(0, y - viewport_height // 3)
                )

        QTimer.singleShot(0, scroll)

    def load_week_view(self):
        """Aggregate and display the week containing the selected date"""
        monday = self.current_date - timedelta(days=self.current_date.weekday())
        sunday = monday + timedelta(days=6)

        activities = self._load_range(monday, sunday)
        projects = self.database.get_projects()
        project_map = {p['id']: p for p in projects}

        day_project_seconds: dict[date, dict] = {}
        for activity in activities:
            if activity.get('is_idle', False):
                continue

            day = activity['timestamp'].date()
            key = activity.get('project_id')
            day_data = day_project_seconds.setdefault(day, {})
            day_data[key] = day_data.get(key, 0) + activity['duration']

        self.week_view.set_data(monday, day_project_seconds, project_map)
        self._update_range_stats(activities, f"KW {monday.isocalendar()[1]}")

    def load_month_view(self):
        """Aggregate and display the month containing the selected date"""
        first_day = self.current_date.replace(day=1)
        if first_day.month == 12:
            next_month = first_day.replace(year=first_day.year + 1, month=1)
        else:
            next_month = first_day.replace(month=first_day.month + 1)
        last_day = next_month - timedelta(days=1)

        activities = self._load_range(first_day, last_day)

        day_seconds: dict[date, int] = {}
        for activity in activities:
            if activity.get('is_idle', False):
                continue
            day = activity['timestamp'].date()
            day_seconds[day] = day_seconds.get(day, 0) + activity['duration']

        self.month_view.set_data(first_day, day_seconds)
        self._update_range_stats(activities, first_day.strftime('%B %Y'))

    def _update_range_stats(self, activities: list[dict], label: str):
        """Show summary stats for week/month views in the bottom bar"""
        active_seconds = sum(
            a['duration'] for a in activities if not a.get('is_idle', False)
        )
        days_with_data = len({
            a['timestamp'].date() for a in activities
            if not a.get('is_idle', False)
        })
        avg = active_seconds / days_with_data / 3600 if days_with_data else 0

        self.stats_label.setText(
            f"{label} | Aktiv: {active_seconds / 3600:.1f}h | "
            f"Tage mit Daten: {days_with_data} | Ø pro Tag: {avg:.1f}h"
        )

    # ------------------------------------------------------------------
    # Stats & filters (day view)
    # ------------------------------------------------------------------

    def update_stats(self, all_activities: list[dict], filtered_count: int):
        """Update statistics display"""
        if not all_activities:
            self.stats_label.setText("Keine Aktivitäten für diesen Tag")
            return

        total_seconds = sum(a["duration"] for a in all_activities)
        active_seconds = sum(
            a["duration"] for a in all_activities
            if not a.get("is_idle", False)
        )

        total_hours = total_seconds / 3600
        active_hours = active_seconds / 3600
        idle_hours = (total_seconds - active_seconds) / 3600

        filter_info = ""
        if filtered_count < len(all_activities):
            filter_info = f" (Filter: {filtered_count} Aktivitäten)"

        self.stats_label.setText(
            f"Gesamt: {total_hours:.1f}h | "
            f"Aktiv: {active_hours:.1f}h | "
            f"Idle: {idle_hours:.1f}h | "
            f"Aktivitäten: {len(all_activities)}{filter_info}"
        )

    def update_filter_options(self, all_activities: list[dict], projects: list[dict]):
        """Update filter dropdown options from already loaded day data"""
        apps = sorted({a["app_name"] for a in all_activities})
        current_app = self.app_filter.currentData()

        self.app_filter.blockSignals(True)
        self.app_filter.clear()
        self.app_filter.addItem("Alle", None)
        for app in apps:
            self.app_filter.addItem(app, app)

        if current_app:
            index = self.app_filter.findData(current_app)
            if index >= 0:
                self.app_filter.setCurrentIndex(index)

        self.app_filter.blockSignals(False)

        current_project = self.project_filter.currentData()

        self.project_filter.blockSignals(True)
        self.project_filter.clear()
        self.project_filter.addItem("Alle", None)
        self.project_filter.addItem("Ohne Projekt", "NO_PROJECT")
        for project in projects:
            self.project_filter.addItem(project["name"], project["id"])

        if current_project:
            index = self.project_filter.findData(current_project)
            if index >= 0:
                self.project_filter.setCurrentIndex(index)

        self.project_filter.blockSignals(False)

    def apply_filters(self):
        """Apply selected filters"""
        self.load_current_view()

    def clear_filters(self):
        """Clear all filters"""
        self.app_filter.setCurrentIndex(0)
        self.project_filter.setCurrentIndex(0)

    def update_recent_projects_bar(self):
        """Update the recently used projects bar"""
        while self.recent_projects_layout.count():
            child = self.recent_projects_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        recent_projects = self.database.get_recently_used_projects(limit=10)

        for project in recent_projects:
            project_widget = ProjectDropWidget(
                self.database,
                project['id'],
                project['name'],
                on_assigned=self.on_drop_assignment,
            )
            project_widget.setFixedHeight(30)
            project_widget.setMinimumWidth(80)
            project_widget.setMaximumWidth(150)
            project_widget.setStyleSheet(
                f"background-color: {project['color']}; "
                "border-radius: 5px; padding: 5px 10px; color: white; font-weight: bold;"
            )

            project_label = QLabel()
            project_label.setStyleSheet("color: white; font-weight: bold;")
            project_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            project_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            project_label.setWordWrap(False)

            label_font = project_label.font()
            label_font.setBold(True)
            project_label.setFont(label_font)
            fm = QFontMetrics(label_font)
            elided_name = fm.elidedText(project['name'], Qt.TextElideMode.ElideRight, 130)
            project_label.setText(elided_name)
            project_label.setToolTip(project['name'])

            project_layout = QHBoxLayout(project_widget)
            project_layout.setContentsMargins(5, 0, 5, 0)
            project_layout.addWidget(project_label)

            self.recent_projects_layout.addWidget(project_widget)

        if recent_projects:
            self.recent_projects_layout.addStretch()

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def push_undo(self, action: dict):
        """Store an undoable action (assign or delete)"""
        self.undo_stack.append(action)
        if len(self.undo_stack) > MAX_UNDO_STEPS:
            self.undo_stack.pop(0)

    def on_drop_assignment(self, action: dict):
        """Drag & drop assignment happened: record undo and refresh"""
        self.push_undo(action)
        self.load_current_view()

    def undo_last_action(self):
        """Undo the most recent assign/delete action (Ctrl+Z)"""
        if not self.undo_stack:
            return

        action = self.undo_stack.pop()

        if action['type'] == 'delete':
            restored = self.database.restore_activities(action['rows'])
            logger.info(f"Undo: {restored} Aktivitäten wiederhergestellt")
        elif action['type'] == 'assign':
            for activity_id, old_project_id in action['changes']:
                self.database.assign_activity_to_project(
                    activity_id, old_project_id, update_last_used=False
                )
            logger.info(f"Undo: {len(action['changes'])} Zuordnungen zurückgesetzt")

        self.load_current_view()

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def zoom_in(self):
        """Zoom in (increase hour height)"""
        self.zoom_slider.setValue(min(self.zoom_slider.value() + 10, ZOOM_MAX))

    def zoom_out(self):
        """Zoom out (decrease hour height)"""
        self.zoom_slider.setValue(max(self.zoom_slider.value() - 10, ZOOM_MIN))

    def zoom_changed(self, value):
        """Handle zoom slider change"""
        self.timeline.set_zoom(value)

    def eventFilter(self, obj, event):
        """Handle Ctrl+Wheel zoom anchored at the cursor position"""
        if event.type() == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if self.current_view() == VIEW_DAY:
                    self._zoom_at_cursor(event.angleDelta().y())
                event.accept()
                return True
        return super().eventFilter(obj, event)

    def _zoom_at_cursor(self, delta: int):
        """Zoom while keeping the time under the mouse cursor stable"""
        old_height = self.timeline.hour_height
        step = 5 if delta > 0 else -5
        new_height = min(ZOOM_MAX, max(ZOOM_MIN, old_height + step))

        if new_height == old_height:
            return

        viewport = self.scroll_area.viewport()
        cursor_y = viewport.mapFromGlobal(QCursor.pos()).y()
        cursor_y = min(max(cursor_y, 0), viewport.height())

        scrollbar = self.scroll_area.verticalScrollBar()
        timeline_y = scrollbar.value() + cursor_y
        hours_at_cursor = (
            (timeline_y - self.timeline.top_margin) / old_height
        )

        # Triggers timeline.set_zoom via valueChanged
        self.zoom_slider.setValue(new_height)

        def restore_anchor():
            new_y = self.timeline.top_margin + hours_at_cursor * new_height
            scrollbar.setValue(int(new_y - cursor_y))

        # Wait one event loop cycle so the scroll range is updated first
        QTimer.singleShot(0, restore_anchor)

    # ------------------------------------------------------------------
    # Selection helpers (sidebar clicks)
    # ------------------------------------------------------------------

    def select_app_activities(self, app_name: str):
        """Select all activities for a specific app"""
        app_index = self.app_filter.findData(app_name)
        if app_index >= 0:
            self.app_filter.setCurrentIndex(app_index)

        filtered = self._apply_activity_filters(self._day_activities)
        matching = [a for a in filtered if a["app_name"] == app_name]
        self.timeline.select_all_activities(matching)

    def select_file_activities(self, filename: str):
        """Select all activities for a specific file"""
        filtered = self._apply_activity_filters(self._day_activities)

        matching = []
        for activity in filtered:
            window_title = activity.get("window_title", "")
            if window_title and extract_filename_from_title(window_title) == filename:
                matching.append(activity)

        self.timeline.select_all_activities(matching)

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def open_project_manager(self):
        """Open project management dialog"""
        dialog = ProjectManagerDialog(self.database, self)
        dialog.exec()
        self.load_current_view()

    def open_rules_dialog(self):
        """Open assignment rules dialog"""
        dialog = RulesDialog(self.database, self)
        dialog.exec()
        # Tracker uses a cached rule set; refresh it after changes
        self.tracker.rules_engine.reload()
        self.load_current_view()

    def open_manual_entry(self, start: Optional[datetime] = None):
        """Open manual entry dialog (button, Ctrl+N, or timeline double click)"""
        dialog = ManualEntryDialog(self.database, start=start, parent=self)
        if dialog.exec():
            self.load_current_view()

    def open_calendar_import(self):
        """Open ICS calendar import dialog"""
        dialog = CalendarImportDialog(self.database, self)
        if dialog.exec():
            self.load_current_view()

    def open_export_dialog(self):
        """Open export dialog"""
        dialog = ExportDialog(self.database, self)
        dialog.exec()

    def open_settings(self):
        """Open settings dialog and apply changes live"""
        dialog = SettingsDialog(self.database, self)
        if dialog.exec():
            self.apply_runtime_settings()
            self.load_current_view()

    def apply_runtime_settings(self):
        """Apply saved settings to running components without restart"""
        self.tracker.poll_interval = get_env_int('POLL_INTERVAL', 2)
        self.tracker.idle_threshold = get_env_int('IDLE_THRESHOLD', 300)
        self.timeline.reload_settings()

    def open_assignment_suggestions(self):
        """Open the suggestions dialog; applied suggestions are undoable"""
        dialog = AssignmentSuggestionsDialog(self.database, self)
        if dialog.exec():
            if dialog.applied_changes:
                self.push_undo({'type': 'assign', 'changes': dialog.applied_changes})
            self.load_current_view()
