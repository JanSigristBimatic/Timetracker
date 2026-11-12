import logging
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from PyQt6.QtCore import QLockFile, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from core.database import Database
from core.tracker import ActivityTracker
from gui.main_window import MainWindow
from gui.settings_dialog import DAILY_GOAL_SETTING_KEY
from gui.theme import get_theme
from utils.config import get_env_int, get_user_env_path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables: project .env first (development),
# then the user settings file which takes precedence
load_dotenv(BASE_DIR / '.env')
load_dotenv(get_user_env_path(), override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


class TimeTrackerApp:
    """Main application class for TimeTracker.

    This class initializes and manages the main application components:
    - Database connection
    - Activity tracker
    - Main window
    - System tray icon
    """

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("TimeTracker")
        self.app.setQuitOnLastWindowClosed(False)

        # Initialize and apply theme
        self.theme_manager = get_theme()
        self.theme_manager.apply_theme()

        # Initialize database
        try:
            self.database = Database()
            logger.info("Database connection established")
        except Exception as e:
            logger.critical(f"Database connection failed: {e}")
            QMessageBox.critical(
                None,
                "Datenbankfehler",
                f"Datenbankverbindung fehlgeschlagen: {e}\n\n"
                "Bitte stellen Sie sicher, dass die Datenbank korrekt konfiguriert ist."
            )
            sys.exit(1)

        # Initialize activity tracker with configured settings
        self.tracker = ActivityTracker(
            self.database,
            poll_interval=get_env_int('POLL_INTERVAL', 2),
            idle_threshold=get_env_int('IDLE_THRESHOLD', 300),
        )

        # Initialize main window
        self.main_window = MainWindow(self.database, self.tracker)

        # Daily goal notification state
        self._goal_notified_date = None

        # Initialize system tray
        self.setup_system_tray()

        # Start tracking
        self.tracker.start()

        # Show main window on startup
        self.main_window.show()

    def setup_system_tray(self):
        """Setup system tray icon and menu"""
        self.tray_icon = QSystemTrayIcon(self.app)

        # Resolve icon relative to the project root so it works
        # regardless of the current working directory
        icon = QIcon(str(BASE_DIR / 'resources' / 'icons' / 'tray_icon.png'))
        self.tray_icon.setIcon(icon)
        self.app.setWindowIcon(icon)

        # Create tray menu
        tray_menu = QMenu()

        show_action = QAction("Öffnen", self.app)
        show_action.triggered.connect(self.show_main_window)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        self.pause_action = QAction("Tracking pausieren", self.app)
        self.pause_action.triggered.connect(self.toggle_tracking)
        tray_menu.addAction(self.pause_action)

        tray_menu.addSeparator()

        quit_action = QAction("Beenden", self.app)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

        self.update_tray_tooltip()

        self.tooltip_timer = QTimer()
        self.tooltip_timer.timeout.connect(self.update_tray_tooltip)
        self.tooltip_timer.start(10000)  # Update every 10 seconds

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

    def _today_active_hours(self) -> float:
        """Sum of today's active (non-idle) time in hours"""
        today = date.today()
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        return self.database.get_total_duration(start, end) / 3600

    def _daily_goal_hours(self) -> float:
        """Configured daily goal in hours (0 = disabled)"""
        try:
            return float(self.database.get_setting(DAILY_GOAL_SETTING_KEY) or '0')
        except (TypeError, ValueError):
            return 0.0

    def update_tray_tooltip(self):
        """Update tray tooltip with today's total and the current activity"""
        active_hours = self._today_active_hours()
        goal = self._daily_goal_hours()

        if goal > 0:
            summary = f"Heute: {active_hours:.1f}h / {goal:.1f}h"
        else:
            summary = f"Heute: {active_hours:.1f}h"

        if self.tracker.is_running:
            current = self.tracker.get_current_activity()
            if current:
                tooltip = f"TimeTracker - {summary}\n{current['app_name']}"
                if current['window_title']:
                    tooltip += f"\n{current['window_title'][:50]}"
            else:
                tooltip = f"TimeTracker - {summary}\n(Idle)"
        else:
            tooltip = f"TimeTracker - Pausiert\n{summary}"

        self.tray_icon.setToolTip(tooltip)

        self._check_daily_goal(active_hours, goal)

    def _check_daily_goal(self, active_hours: float, goal: float):
        """Notify once per day when the daily goal is reached"""
        if goal <= 0 or active_hours < goal:
            return

        today = date.today()
        if self._goal_notified_date == today:
            return

        self._goal_notified_date = today
        self.tray_icon.showMessage(
            "Tagesziel erreicht",
            f"Du hast heute {active_hours:.1f}h aktiv gearbeitet "
            f"(Ziel: {goal:.1f}h).",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

    def quit_app(self):
        """Quit application"""
        self.main_window.save_window_state()
        self.tracker.stop()
        self.database.close()
        self.tray_icon.hide()
        self.app.quit()

    def run(self):
        """Run the application"""
        return self.app.exec()


def acquire_single_instance_lock():
    """Prevent a second instance from tracking in parallel.

    Returns the lock object (must stay referenced) or None if
    another instance is already running.
    """
    lock_dir = Path.home() / '.timetracker'
    lock_dir.mkdir(exist_ok=True)

    lock = QLockFile(str(lock_dir / 'timetracker.lock'))
    lock.setStaleLockTime(0)  # Locks from crashed processes are detected

    if not lock.tryLock(100):
        return None
    return lock


def main():
    lock = acquire_single_instance_lock()
    if lock is None:
        # Need a QApplication for the message box
        app = QApplication(sys.argv)
        QMessageBox.warning(
            None,
            "TimeTracker läuft bereits",
            "TimeTracker ist bereits gestartet.\n"
            "Ein zweiter Start würde doppelte Einträge erzeugen."
        )
        sys.exit(0)

    app = TimeTrackerApp()
    exit_code = app.run()
    lock.unlock()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
