import logging
import platform
import time
from datetime import datetime
from threading import Event, Lock, Thread
from typing import Optional

from core.database_protocol import DatabaseProtocol
from utils.config import should_ignore_activity
from utils.social_media_detector import SocialMediaDetector

logger = logging.getLogger(__name__)


class ActivityTracker:
    """Main activity tracker that works across platforms.

    This class manages activity tracking in a background thread and provides
    thread-safe access to the current activity state.
    """

    def __init__(
        self, database: DatabaseProtocol, poll_interval: int = 2, idle_threshold: int = 300
    ):
        """
        Initialize activity tracker.

        Args:
            database: Database instance for storing activities
            poll_interval: How often to check for window changes (seconds)
            idle_threshold: Seconds of inactivity before marking as idle
        """
        self.database = database
        self.poll_interval = poll_interval
        self.idle_threshold = idle_threshold

        self._current_activity: Optional[dict] = None
        self._start_time: Optional[datetime] = None
        self._activity_lock = Lock()

        self.is_running = False
        self.stop_event = Event()
        self.tracker_thread: Optional[Thread] = None

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
        """Stop tracking and save any pending activity."""
        if not self.is_running:
            return

        self.is_running = False
        self.stop_event.set()

        # Save current activity before stopping
        with self._activity_lock:
            if self._current_activity and self._start_time:
                self._save_current_activity()

        if self.tracker_thread:
            self.tracker_thread.join(timeout=5)

    def _track_loop(self):
        """Main tracking loop that monitors window changes and idle state.

        This method runs in a background thread and periodically checks for:
        - Active window changes
        - User idle state (no input + no audio)

        All access to shared state is protected by _activity_lock.
        """
        while not self.stop_event.is_set():
            try:
                current = self.platform_tracker.get_active_window()

                # Skip ignored processes
                if current and should_ignore_activity(
                    current['app_name'], current.get('window_title', '')
                ):
                    current = None

                with self._activity_lock:
                    # Check if activity changed
                    if current and self._is_activity_different(current):
                        # Save previous activity
                        if self._current_activity and self._start_time:
                            self._save_current_activity()

                        # Start tracking new activity
                        self._current_activity = current
                        self._start_time = datetime.now()

                    # Check for idle time
                    idle_time = self.platform_tracker.get_idle_time()
                    is_audio_playing = self.platform_tracker.is_audio_playing()

                    # Consider idle only if: no input AND no audio playing
                    if idle_time > self.idle_threshold and not is_audio_playing:
                        if self._current_activity and not self._current_activity.get('is_idle'):
                            # Mark as idle
                            self._save_current_activity(is_idle=True)
                            self._current_activity = None
                            self._start_time = None

            except Exception as e:
                logger.error(f"Error in tracking loop: {e}")

            time.sleep(self.poll_interval)

    def _is_activity_different(self, new_activity: dict) -> bool:
        """Check if the new activity is different from current.

        Args:
            new_activity: Activity dict with 'app_name' and 'window_title' keys

        Returns:
            True if the activity has changed, False otherwise

        Note:
            Must be called with _activity_lock held.
        """
        if not self._current_activity:
            return True

        return (
            new_activity['app_name'] != self._current_activity['app_name'] or
            new_activity['window_title'] != self._current_activity['window_title']
        )

    def _save_current_activity(self, is_idle: bool = False) -> None:
        """Save the current activity to database.

        Args:
            is_idle: Whether this activity should be marked as idle time

        Note:
            Must be called with _activity_lock held.
        """
        if not self._current_activity or not self._start_time:
            return

        end_time = datetime.now()

        # Only save if duration is at least 1 second
        if (end_time - self._start_time).total_seconds() >= 1:
            activity_id = self.database.save_activity(
                app_name=self._current_activity['app_name'],
                window_title=self._current_activity['window_title'],
                start_time=self._start_time,
                end_time=end_time,
                is_idle=is_idle,
                process_path=self._current_activity.get('process_path')
            )

            # Auto-assign to Social Media project if detected
            if activity_id and SocialMediaDetector.is_social_media(
                self._current_activity['app_name'],
                self._current_activity['window_title']
            ):
                social_media_project_id = self.database.get_social_media_project_id()
                if social_media_project_id:
                    self.database.assign_activity_to_project(
                        activity_id, social_media_project_id
                    )

    def get_current_activity(self) -> Optional[dict]:
        """Get the current activity being tracked (thread-safe).

        Returns:
            Copy of current activity dict or None if no activity is tracked
        """
        with self._activity_lock:
            if self._current_activity:
                return self._current_activity.copy()
            return None
