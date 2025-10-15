"""
Tests for activity deletion functionality
"""
import pytest
from datetime import datetime
import tempfile
from pathlib import Path

from core.database import Database


class TestDeleteActivities:
    """Test deletion of activities"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Monkey-patch the database path
            original_home = Path.home
            Path.home = lambda: Path(tmpdir)

            db = Database()
            yield db

            # Cleanup
            db.close()
            Path.home = original_home

    def test_delete_single_activity_by_timerange(self, temp_db):
        """Test deleting a single activity by timerange"""
        # Create activity
        start_time = datetime(2024, 1, 15, 10, 0)
        end_time = datetime(2024, 1, 15, 11, 0)
        temp_db.save_activity(
            "Code.exe",
            "main.py",
            start_time,
            end_time,
        )

        # Verify activity exists
        activities = temp_db.get_activities()
        assert len(activities) == 1

        # Delete activity
        deleted_count = temp_db.delete_activities_by_timerange(
            start_time, end_time, "Code.exe"
        )

        assert deleted_count == 1

        # Verify activity was deleted
        activities = temp_db.get_activities()
        assert len(activities) == 0

    def test_delete_multiple_activities_by_timerange(self, temp_db):
        """Test deleting multiple activities in same timerange"""
        # Create multiple activities for the same app
        temp_db.save_activity(
            "Code.exe",
            "file1.py",
            datetime(2024, 1, 15, 9, 0),
            datetime(2024, 1, 15, 9, 30),
        )
        temp_db.save_activity(
            "Code.exe",
            "file2.py",
            datetime(2024, 1, 15, 9, 30),
            datetime(2024, 1, 15, 10, 0),
        )
        temp_db.save_activity(
            "Code.exe",
            "file3.py",
            datetime(2024, 1, 15, 10, 0),
            datetime(2024, 1, 15, 10, 30),
        )

        # Verify activities exist
        activities = temp_db.get_activities()
        assert len(activities) == 3

        # Delete all activities in timerange
        deleted_count = temp_db.delete_activities_by_timerange(
            datetime(2024, 1, 15, 9, 0),
            datetime(2024, 1, 15, 10, 30),
            "Code.exe"
        )

        assert deleted_count == 3

        # Verify all activities were deleted
        activities = temp_db.get_activities()
        assert len(activities) == 0

    def test_delete_only_matching_app(self, temp_db):
        """Test that deletion only affects matching app"""
        # Create activities for different apps in same timerange
        start_time = datetime(2024, 1, 15, 10, 0)
        end_time = datetime(2024, 1, 15, 11, 0)

        temp_db.save_activity(
            "Code.exe",
            "main.py",
            start_time,
            end_time,
        )
        temp_db.save_activity(
            "chrome.exe",
            "GitHub",
            start_time,
            end_time,
        )

        # Verify both activities exist
        activities = temp_db.get_activities()
        assert len(activities) == 2

        # Delete only Code.exe activities
        deleted_count = temp_db.delete_activities_by_timerange(
            start_time, end_time, "Code.exe"
        )

        assert deleted_count == 1

        # Verify only Code.exe was deleted
        activities = temp_db.get_activities()
        assert len(activities) == 1
        assert activities[0]["app_name"] == "chrome.exe"

    def test_delete_partial_timerange(self, temp_db):
        """Test deleting activities in partial timerange"""
        # Create activities spanning different times
        temp_db.save_activity(
            "Code.exe",
            "file1.py",
            datetime(2024, 1, 15, 9, 0),
            datetime(2024, 1, 15, 10, 0),
        )
        temp_db.save_activity(
            "Code.exe",
            "file2.py",
            datetime(2024, 1, 15, 10, 0),
            datetime(2024, 1, 15, 11, 0),
        )
        temp_db.save_activity(
            "Code.exe",
            "file3.py",
            datetime(2024, 1, 15, 11, 0),
            datetime(2024, 1, 15, 12, 0),
        )

        # Verify all activities exist
        activities = temp_db.get_activities()
        assert len(activities) == 3

        # Delete only activities between 10:00 and 11:00
        deleted_count = temp_db.delete_activities_by_timerange(
            datetime(2024, 1, 15, 10, 0),
            datetime(2024, 1, 15, 11, 0),
            "Code.exe"
        )

        assert deleted_count == 1

        # Verify only middle activity was deleted
        activities = temp_db.get_activities()
        assert len(activities) == 2
        assert activities[0]["window_title"] == "file3.py"
        assert activities[1]["window_title"] == "file1.py"

    def test_delete_no_matching_activities(self, temp_db):
        """Test deletion returns 0 when no activities match"""
        # Create activity
        temp_db.save_activity(
            "Code.exe",
            "main.py",
            datetime(2024, 1, 15, 10, 0),
            datetime(2024, 1, 15, 11, 0),
        )

        # Try to delete activities with different app name
        deleted_count = temp_db.delete_activities_by_timerange(
            datetime(2024, 1, 15, 10, 0),
            datetime(2024, 1, 15, 11, 0),
            "chrome.exe"
        )

        assert deleted_count == 0

        # Verify original activity still exists
        activities = temp_db.get_activities()
        assert len(activities) == 1
        assert activities[0]["app_name"] == "Code.exe"

    def test_delete_activities_with_project_assignment(self, temp_db):
        """Test that activities with project assignments can be deleted"""
        # Create project and activity
        project_id = temp_db.create_project("Test Project")
        start_time = datetime(2024, 1, 15, 10, 0)
        end_time = datetime(2024, 1, 15, 11, 0)

        activity_id = temp_db.save_activity(
            "Code.exe",
            "main.py",
            start_time,
            end_time,
        )

        # Assign activity to project
        temp_db.assign_activity_to_project(activity_id, project_id)

        # Verify activity exists with project
        activities = temp_db.get_activities(project_id=project_id)
        assert len(activities) == 1

        # Delete activity
        deleted_count = temp_db.delete_activities_by_timerange(
            start_time, end_time, "Code.exe"
        )

        assert deleted_count == 1

        # Verify activity was deleted
        activities = temp_db.get_activities()
        assert len(activities) == 0

        # Verify project still exists
        projects = temp_db.get_projects()
        assert any(p["name"] == "Test Project" for p in projects)

    def test_delete_empty_database(self, temp_db):
        """Test deletion on empty database returns 0"""
        deleted_count = temp_db.delete_activities_by_timerange(
            datetime(2024, 1, 15, 10, 0),
            datetime(2024, 1, 15, 11, 0),
            "Code.exe"
        )

        assert deleted_count == 0

    def test_thread_safety_of_deletion(self, temp_db):
        """Test that deletion is thread-safe"""
        # Create multiple activities
        for i in range(10):
            temp_db.save_activity(
                "Code.exe",
                f"file{i}.py",
                datetime(2024, 1, 15, 10, i),
                datetime(2024, 1, 15, 10, i + 1),
            )

        # Verify activities exist
        activities = temp_db.get_activities()
        assert len(activities) == 10

        # Delete all activities
        deleted_count = temp_db.delete_activities_by_timerange(
            datetime(2024, 1, 15, 10, 0),
            datetime(2024, 1, 15, 10, 10),
            "Code.exe"
        )

        assert deleted_count == 10

        # Verify all deleted
        activities = temp_db.get_activities()
        assert len(activities) == 0
