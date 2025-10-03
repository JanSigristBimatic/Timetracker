import sys
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer
from core.database import Database
from core.tracker import ActivityTracker
from gui.main_window import MainWindow


class TimeTrackerApp:
    """Main application class"""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("TimeTracker")
        self.app.setQuitOnLastWindowClosed(False)

        # Initialize database
        try:
            self.database = Database()
        except Exception as e:
            print(f"Database connection failed: {e}")
            print("Please ensure PostgreSQL is running and configured correctly.")
            sys.exit(1)

        # Initialize activity tracker
        self.tracker = ActivityTracker(self.database)

        # Initialize main window
        self.main_window = MainWindow(self.database, self.tracker)

        # Initialize system tray
        self.setup_system_tray()

        # Start tracking
        self.tracker.start()

        # Show main window on startup
        self.main_window.show()

    def setup_system_tray(self):
        """Setup system tray icon and menu"""
        self.tray_icon = QSystemTrayIcon(self.app)

        # Set custom icon
        icon = QIcon("resources/icons/tray_icon.png")
        self.tray_icon.setIcon(icon)
        self.app.setWindowIcon(icon)

        # Create tray menu
        tray_menu = QMenu()

        # Show window action
        show_action = QAction("Öffnen", self.app)
        show_action.triggered.connect(self.show_main_window)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        # Pause/Resume tracking
        self.pause_action = QAction("Tracking pausieren", self.app)
        self.pause_action.triggered.connect(self.toggle_tracking)
        tray_menu.addAction(self.pause_action)

        tray_menu.addSeparator()

        # Quit action
        quit_action = QAction("Beenden", self.app)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

        # Set tooltip
        self.update_tray_tooltip()

        # Update tooltip periodically
        self.tooltip_timer = QTimer()
        self.tooltip_timer.timeout.connect(self.update_tray_tooltip)
        self.tooltip_timer.start(5000)  # Update every 5 seconds

    def tray_icon_activated(self, reason):
        """Handle tray icon click"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_main_window()

    def show_main_window(self):
        """Show and bring main window to front"""
        self.main_window.show()
        self.main_window.activateWindow()
        self.main_window.raise_()

    def toggle_tracking(self):
        """Toggle tracking on/off"""
        if self.tracker.is_running:
            self.tracker.stop()
            self.pause_action.setText("Tracking fortsetzen")
        else:
            self.tracker.start()
            self.pause_action.setText("Tracking pausieren")

        self.update_tray_tooltip()

    def update_tray_tooltip(self):
        """Update system tray tooltip with current activity"""
        if self.tracker.is_running:
            current = self.tracker.get_current_activity()
            if current:
                tooltip = f"TimeTracker - Aktiv\n{current['app_name']}"
                if current['window_title']:
                    tooltip += f"\n{current['window_title'][:50]}"
            else:
                tooltip = "TimeTracker - Aktiv (Idle)"
        else:
            tooltip = "TimeTracker - Pausiert"

        self.tray_icon.setToolTip(tooltip)

    def quit_app(self):
        """Quit application"""
        self.tracker.stop()
        self.database.close()
        self.app.quit()

    def run(self):
        """Run the application"""
        return self.app.exec()


def main():
    app = TimeTrackerApp()
    sys.exit(app.run())


if __name__ == '__main__':
    main()
