import logging
import platform
from datetime import datetime, timedelta
from threading import Event, Lock, Thread
from typing import Optional

from core.database_protocol import DatabaseProtocol
from utils.assignment_rules import AssignmentRulesEngine
from utils.config import should_ignore_activity
from utils.social_media_detector import SocialMediaDetector

logger = logging.getLogger(__name__)

IDLE_APP_NAME = 'Idle'

# A wall clock jump this large between two polls means the loop was not
# running (standby, hibernation). The gap must never count as work.
SUSPEND_GAP_SECONDS = 60


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

        self.rules_engine = AssignmentRulesEngine(database)

        self._current_activity: Optional[dict] = None
        self._start_time: Optional[datetime] = None
        self._idle_since: Optional[datetime] = None
        self._activity_lock = Lock()

        self.is_running = False
        self.stop_event = Event()
        self.tracker_thread: Optional[Thread] = None

        self.platform_tracker = self._get_platform_tracker()

    def _get_platform_tracker(self):
        """Get the appropriate platform-specific tracker"""
        system = platform.system()

        if system == 'Windows':
            from .platform.windows import WindowsActivityTracker
            return WindowsActivityTracker()
        raise NotImplementedError(f"Tracking is not implemented for {system}")

    def start(self):
        """Start tracking in background thread"""
        if self.is_running:
            return

        self.is_running = True
        self.stop_event.clear()
        self.tracker_thread = Thread(target=self._track_loop, daemon=True)
        self.tracker_thread.start()

    def stop(self):
        """Stop tracking and close the pending activity or idle period.

        The state is reset afterwards so a later start() never extends
        an activity across the paused time.
        """
        if not self.is_running:
            return

        self.is_running = False
        self.stop_event.set()

        if self.tracker_thread:
            self.tracker_thread.join(timeout=5)

        with self._activity_lock:
            self._close_open_period(end_time=datetime.now())

    def _track_loop(self):
        """Main tracking loop that monitors window changes and idle state.

        This method runs in a background thread and periodically checks for:
        - Suspend gaps (standby, hibernation)
        - Active window changes
        - User idle state (no input and no audio from the foreground app)

        All access to shared state is protected by _activity_lock.
        """
        last_poll = datetime.now()

        while not self.stop_event.is_set():
            try:
                now = datetime.now()
                self._handle_suspend_gap(last_poll, now)
                last_poll = now

                current = self.platform_tracker.get_active_window()

                if current and should_ignore_activity(
                    current['app_name'], current.get('window_title', '')
                ):
                    current = None

                # Read idle/audio state outside the lock (these can be slow)
                idle_time = self.platform_tracker.get_idle_time()
                foreground_app = current['app_name'] if current else None
                is_audio_playing = self.platform_tracker.is_audio_playing(foreground_app)
                is_idle_now = (
                    idle_time > self.idle_threshold and not is_audio_playing
                )

                with self._activity_lock:
                    if is_idle_now:
                        self._enter_idle_state(idle_time)
                    else:
                        self._exit_idle_state()

                        if current and self._is_activity_different(current):
                            # One timestamp ends the old and starts the new
                            # activity, so consecutive blocks have no gaps
                            self._save_current_activity(end_time=now)
                            self._current_activity = current
                            self._start_time = now

            except Exception as e:
                logger.error(f"Error in tracking loop: {e}")

            self.stop_event.wait(self.poll_interval)

    def _handle_suspend_gap(self, last_poll: datetime, now: datetime) -> None:
        """Close the running activity at the last poll if the loop was frozen.

        The frozen time is stored as idle, so it shows up as a gap in the
        timeline instead of being added to the activity that was active
        before the computer went to sleep.
        """
        if (now - last_poll).total_seconds() < SUSPEND_GAP_SECONDS:
            return

        logger.info(f"Suspend gap detected: {last_poll} -> {now}")
        with self._activity_lock:
            if self._idle_since is not None:
                return  # The idle period already covers the gap

            self._save_current_activity(end_time=last_poll)
            self._current_activity = None
            self._start_time = None
            self._idle_since = last_poll

    def _close_open_period(self, end_time: datetime) -> None:
        """Save the open activity or idle period and reset the state.

        Note:
            Must be called with _activity_lock held.
        """
        if self._idle_since is not None:
            self._save_idle_period(end_time=end_time)
        else:
            self._save_current_activity(end_time=end_time)

        self._current_activity = None
        self._start_time = None
        self._idle_since = None

    def _enter_idle_state(self, idle_time: float) -> None:
        """Handle transition into idle: close the active work at the
        moment input stopped, so idle time never counts as work.

        Note:
            Must be called with _activity_lock held.
        """
        if self._idle_since is not None:
            return  # Already idle, keep waiting

        idle_started = datetime.now() - timedelta(seconds=idle_time)

        if self._current_activity and self._start_time:
            self._save_current_activity(end_time=idle_started)

        self._current_activity = None
        self._start_time = None
        self._idle_since = idle_started

    def _exit_idle_state(self) -> None:
        """Handle transition out of idle: store the idle period as its
        own block so the timeline shows the gap explicitly.

        Note:
            Must be called with _activity_lock held.
        """
        if self._idle_since is None:
            return

        self._save_idle_period(end_time=datetime.now())
        self._idle_since = None

    def _save_idle_period(self, end_time: datetime) -> None:
        """Save the elapsed idle period as an idle activity.

        Note:
            Must be called with _activity_lock held.
        """
        if self._idle_since is None:
            return

        if (end_time - self._idle_since).total_seconds() >= 1:
            self.database.save_activity(
                app_name=IDLE_APP_NAME,
                window_title='',
                start_time=self._idle_since,
                end_time=end_time,
                is_idle=True,
            )

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

    def _save_current_activity(self, end_time: Optional[datetime] = None) -> None:
        """Save the current activity to database.

        Args:
            end_time: Optional explicit end (defaults to now); used to
                cut the activity at the moment the user went idle

        Note:
            Must be called with _activity_lock held.
        """
        if not self._current_activity or not self._start_time:
            return

        if end_time is None:
            end_time = datetime.now()

        if (end_time - self._start_time).total_seconds() < 1:
            return

        activity_id = self.database.save_activity(
            app_name=self._current_activity['app_name'],
            window_title=self._current_activity['window_title'],
            start_time=self._start_time,
            end_time=end_time,
            process_path=self._current_activity.get('process_path')
        )

        if activity_id:
            self._auto_assign_project(
                activity_id,
                self._current_activity['app_name'],
                self._current_activity['window_title'],
            )

    def _auto_assign_project(
        self, activity_id: int, app_name: str, window_title: str
    ) -> None:
        """Assign a freshly saved activity via rules or social media detection.

        Deterministic user rules take precedence over the built-in
        social media detector.
        """
        project_id = self.rules_engine.match(app_name, window_title)

        if project_id is None and SocialMediaDetector.is_social_media(
            app_name, window_title
        ):
            project_id = self.database.get_social_media_project_id()

        if project_id is not None:
            self.database.assign_activity_to_project(
                activity_id, project_id, update_last_used=False
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
