"""
Tests for activity tracker
"""
import pytest
from datetime import datetime
import time
from unittest.mock import Mock, patch

from core.tracker import ActivityTracker


class TestActivityTracker:
    """Test activity tracking functionality"""

    @pytest.fixture
    def mock_platform_tracker(self):
        """Mock platform-specific tracker"""
        mock = Mock()
        mock.get_active_window.return_value = {
            "app_name": "Code.exe",
            "window_title": "main.py - VSCode",
            "process_path": "C:\\Program Files\\VSCode\\Code.exe",
        }
        mock.get_idle_time.return_value = 0
        return mock

    def test_tracker_initialization(self, mock_db):
        """Test tracker initializes correctly"""
        with patch("core.tracker.ActivityTracker._get_platform_tracker"):
            tracker = ActivityTracker(mock_db, poll_interval=1, idle_threshold=60)

            assert tracker.database is mock_db
            assert tracker.poll_interval == 1
            assert tracker.idle_threshold == 60
            assert not tracker.is_running

    def test_start_tracking(self, mock_db, mock_platform_tracker):
        """Test starting the tracker"""
        with patch("core.tracker.ActivityTracker._get_platform_tracker") as mock_get:
            mock_get.return_value = mock_platform_tracker

            tracker = ActivityTracker(mock_db, poll_interval=0.1)
            tracker.start()

            assert tracker.is_running
            assert tracker.tracker_thread is not None
            assert tracker.tracker_thread.is_alive()

            # Give it time to track
            time.sleep(0.3)

            tracker.stop()

    def test_stop_tracking(self, mock_db, mock_platform_tracker):
        """Test stopping the tracker"""
        with patch("core.tracker.ActivityTracker._get_platform_tracker") as mock_get:
            mock_get.return_value = mock_platform_tracker

            tracker = ActivityTracker(mock_db, poll_interval=0.1)
            tracker.start()
            time.sleep(0.2)
            tracker.stop()

            assert not tracker.is_running
            assert not tracker.tracker_thread.is_alive()

    def test_activity_tracking(self, mock_db, mock_platform_tracker):
        """Test that activities are tracked and saved"""
        with patch("core.tracker.ActivityTracker._get_platform_tracker") as mock_get, \
             patch("core.tracker.should_ignore_activity", return_value=False):
            mock_get.return_value = mock_platform_tracker

            tracker = ActivityTracker(mock_db, poll_interval=0.05)
            tracker.start()

            # Let it track for a bit (ensure > 1 second for minimum duration)
            time.sleep(1.2)

            # Change to a different window
            mock_platform_tracker.get_active_window.return_value = {
                "app_name": "chrome.exe",
                "window_title": "GitHub - Chrome",
                "process_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            }

            # Let it track the new activity
            time.sleep(1.2)

            tracker.stop()

            # Check that activities were saved
            activities = mock_db.get_activities()
            assert len(activities) >= 1

    def test_activity_change_detection(self, mock_db, mock_platform_tracker):
        """Test that activity changes are detected"""
        with patch("core.tracker.ActivityTracker._get_platform_tracker") as mock_get:
            mock_get.return_value = mock_platform_tracker

            tracker = ActivityTracker(mock_db, poll_interval=0.05)

            # Initial activity
            activity1 = {
                "app_name": "Code.exe",
                "window_title": "main.py",
                "process_path": "C:\\Code.exe",
            }

            # Different app
            activity2 = {
                "app_name": "chrome.exe",
                "window_title": "GitHub",
                "process_path": "C:\\chrome.exe",
            }

            # Same app, different window
            activity3 = {
                "app_name": "Code.exe",
                "window_title": "test.py",
                "process_path": "C:\\Code.exe",
            }

            tracker.current_activity = activity1
            assert not tracker._is_activity_different(activity1)
            assert tracker._is_activity_different(activity2)
            assert tracker._is_activity_different(activity3)

    def test_idle_detection(self, mock_db, mock_platform_tracker):
        """Test idle time detection"""
        with patch("core.tracker.ActivityTracker._get_platform_tracker") as mock_get, \
             patch("core.tracker.should_ignore_activity", return_value=False):
            mock_get.return_value = mock_platform_tracker

            tracker = ActivityTracker(mock_db, poll_interval=0.05, idle_threshold=1)
            tracker.start()

            # Let it track active time (ensure > 1 second for minimum duration)
            time.sleep(1.2)

            # Simulate idle
            mock_platform_tracker.get_idle_time.return_value = 2  # Above threshold

            # Let it detect idle
            time.sleep(0.5)

            tracker.stop()

            # Check that an idle activity was saved
            activities = mock_db.get_activities()
            idle_activities = [a for a in activities if a.get("is_idle")]
            assert len(idle_activities) > 0

    def test_ignored_activities(self, mock_db, mock_platform_tracker):
        """Test that ignored activities are not tracked"""
        with patch("core.tracker.ActivityTracker._get_platform_tracker") as mock_get:
            mock_get.return_value = mock_platform_tracker

            # Mock the ignore check to always return True
            with patch("core.tracker.should_ignore_activity") as mock_ignore:
                mock_ignore.return_value = True

                tracker = ActivityTracker(mock_db, poll_interval=0.1)
                tracker.start()
                time.sleep(0.3)
                tracker.stop()

                # No activities should be saved since everything is ignored
                activities = mock_db.get_activities()
                assert len(activities) == 0

    def test_minimum_duration(self, mock_db, mock_platform_tracker):
        """Test that activities shorter than 1 second are not saved"""
        with patch("core.tracker.ActivityTracker._get_platform_tracker") as mock_get:
            mock_get.return_value = mock_platform_tracker

            tracker = ActivityTracker(mock_db, poll_interval=0.01)
            tracker.current_activity = {
                "app_name": "Code.exe",
                "window_title": "main.py",
                "process_path": "C:\\Code.exe",
            }
            tracker.start_time = datetime.now()

            # Immediately save (less than 1 second)
            time.sleep(0.05)
            tracker._save_current_activity()

            # Should not be saved
            activities = mock_db.get_activities()
            assert len(activities) == 0

    def test_get_current_activity(self, mock_db, mock_platform_tracker):
        """Test getting current activity"""
        with patch("core.tracker.ActivityTracker._get_platform_tracker") as mock_get:
            mock_get.return_value = mock_platform_tracker

            tracker = ActivityTracker(mock_db, poll_interval=0.1)
            tracker.start()

            time.sleep(0.3)

            current = tracker.get_current_activity()
            assert current is not None
            assert current["app_name"] == "Code.exe"

            tracker.stop()

    def test_double_start_ignored(self, mock_db, mock_platform_tracker):
        """Test that starting an already running tracker is ignored"""
        with patch("core.tracker.ActivityTracker._get_platform_tracker") as mock_get:
            mock_get.return_value = mock_platform_tracker

            tracker = ActivityTracker(mock_db, poll_interval=0.1)
            tracker.start()

            # Try to start again
            tracker.start()

            # Should still have only one thread
            assert tracker.is_running

            tracker.stop()

    def test_stop_when_not_running(self, mock_db, mock_platform_tracker):
        """Test that stopping a non-running tracker is safe"""
        with patch("core.tracker.ActivityTracker._get_platform_tracker") as mock_get:
            mock_get.return_value = mock_platform_tracker

            tracker = ActivityTracker(mock_db, poll_interval=0.1)

            # Stop without starting
            tracker.stop()

            # Should not raise any errors
            assert not tracker.is_running
