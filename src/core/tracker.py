import sys
import time
from datetime import datetime
from threading import Thread, Event
import platform
from utils.config import should_ignore_activity


class ActivityTracker:
    """Main activity tracker that works across platforms"""

    def __init__(self, database, poll_interval=2, idle_threshold=300):
        """
        Initialize activity tracker

        Args:
            database: Database instance for storing activities
            poll_interval: How often to check for window changes (seconds)
            idle_threshold: Seconds of inactivity before marking as idle
        """
        self.database = database
        self.poll_interval = poll_interval
        self.idle_threshold = idle_threshold

        self.current_activity = None
        self.start_time = None
        self.is_running = False
        self.stop_event = Event()
        self.tracker_thread = None

        # Import platform-specific tracker
        self.platform_tracker = self._get_platform_tracker()

    def _get_platform_tracker(self):
        """Get the appropriate platform-specific tracker"""
        system = platform.system()

        if system == 'Windows':
            from .platform.windows import WindowsActivityTracker
            return WindowsActivityTracker()
        elif system == 'Darwin':
            # TODO: Implement macOS tracker
            raise NotImplementedError("macOS tracking not yet implemented")
        elif system == 'Linux':
            # TODO: Implement Linux tracker
            raise NotImplementedError("Linux tracking not yet implemented")
        else:
            raise OSError(f"Unsupported platform: {system}")

    def start(self):
        """Start tracking in background thread"""
        if self.is_running:
            return

        self.is_running = True
        self.stop_event.clear()
        self.tracker_thread = Thread(target=self._track_loop, daemon=True)
        self.tracker_thread.start()

    def stop(self):
        """Stop tracking"""
        if not self.is_running:
            return

        self.is_running = False
        self.stop_event.set()

        # Save current activity before stopping
        if self.current_activity and self.start_time:
            self._save_current_activity()

        if self.tracker_thread:
            self.tracker_thread.join(timeout=5)

    def _track_loop(self):
        """Main tracking loop"""
        while not self.stop_event.is_set():
            current = self.platform_tracker.get_active_window()

            # Skip ignored processes
            if current and should_ignore_activity(current['app_name'], current.get('window_title', '')):
                current = None

            # Check if activity changed
            if current and self._is_activity_different(current):
                # Save previous activity
                if self.current_activity and self.start_time:
                    self._save_current_activity()

                # Start tracking new activity
                self.current_activity = current
                self.start_time = datetime.now()

            # Check for idle time
            idle_time = self.platform_tracker.get_idle_time()
            if idle_time > self.idle_threshold:
                if self.current_activity and not self.current_activity.get('is_idle'):
                    # Mark as idle
                    self._save_current_activity(is_idle=True)
                    self.current_activity = None
                    self.start_time = None

            time.sleep(self.poll_interval)

    def _is_activity_different(self, new_activity):
        """Check if the new activity is different from current"""
        if not self.current_activity:
            return True

        return (
            new_activity['app_name'] != self.current_activity['app_name'] or
            new_activity['window_title'] != self.current_activity['window_title']
        )

    def _save_current_activity(self, is_idle=False):
        """Save the current activity to database"""
        if not self.current_activity or not self.start_time:
            return

        end_time = datetime.now()

        # Only save if duration is at least 1 second
        if (end_time - self.start_time).total_seconds() >= 1:
            self.database.save_activity(
                app_name=self.current_activity['app_name'],
                window_title=self.current_activity['window_title'],
                start_time=self.start_time,
                end_time=end_time,
                is_idle=is_idle,
                process_path=self.current_activity.get('process_path')
            )

    def get_current_activity(self):
        """Get the current activity being tracked"""
        return self.current_activity
