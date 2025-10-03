from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDateEdit, QScrollArea, QSlider, QComboBox
)
from PyQt6.QtCore import Qt, QDate, QTimer, QEvent
from datetime import datetime, timedelta
from .timeline import TimelineWidget
from .projects import ProjectManagerDialog
from .export_dialog import ExportDialog


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self, database, tracker):
        super().__init__()
        self.database = database
        self.tracker = tracker
        self.current_date = datetime.now().date()

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

        # Timeline widget
        self.timeline = TimelineWidget(self.database)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.timeline)
        self.scroll_area.setWidgetResizable(True)

        # Install event filter to handle Ctrl+Wheel zoom
        self.scroll_area.viewport().installEventFilter(self)

        layout.addWidget(self.scroll_area)

        # Filter bar
        filter_bar = self.create_filter_bar()
        layout.addLayout(filter_bar)

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

        # Refresh button
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.clicked.connect(self.refresh_timeline)
        layout.addWidget(refresh_btn)

        return layout

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

        activities = self.database.get_activities(
            start_date=start_datetime,
            end_date=end_datetime,
            project_id=selected_project
        )

        # Apply app filter
        selected_app = self.app_filter.currentData()
        if selected_app:
            activities = [a for a in activities if a['app_name'] == selected_app]

        self.timeline.set_activities(activities, self.current_date)
        self.update_stats(activities)
        self.update_filter_options()

    def refresh_timeline(self):
        """Refresh the timeline"""
        self.load_timeline()

    def update_stats(self, activities):
        """Update statistics display"""
        if not activities:
            self.stats_label.setText("Keine Aktivitäten für diesen Tag")
            return

        total_seconds = sum(activity['duration'] for activity in activities)
        active_seconds = sum(
            activity['duration'] for activity in activities
            if not activity.get('is_idle', False)
        )

        total_hours = total_seconds / 3600
        active_hours = active_seconds / 3600
        idle_hours = (total_seconds - active_seconds) / 3600

        stats_text = (
            f"Gesamt: {total_hours:.1f}h | "
            f"Aktiv: {active_hours:.1f}h | "
            f"Idle: {idle_hours:.1f}h | "
            f"Aktivitäten: {len(activities)}"
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

    def eventFilter(self, obj, event):
        """Filter events to handle Ctrl+Wheel zoom without scrolling"""
        if event.type() == QEvent.Type.Wheel and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Forward to timeline widget for zoom handling
            self.timeline.wheelEvent(event)
            return True  # Event handled, don't propagate
        return super().eventFilter(obj, event)

    def update_filter_options(self):
        """Update filter dropdown options based on current date"""
        start_datetime = datetime.combine(self.current_date, datetime.min.time())
        end_datetime = datetime.combine(self.current_date, datetime.max.time())

        # Get all activities for this date
        all_activities = self.database.get_activities(
            start_date=start_datetime,
            end_date=end_datetime
        )

        # Get unique apps
        apps = sorted(set(a['app_name'] for a in all_activities))
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
        for project in projects:
            self.project_filter.addItem(project['name'], project['id'])

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
