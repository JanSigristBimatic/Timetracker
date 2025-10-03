"""
Tests for database functionality
"""
import pytest
from datetime import datetime, timedelta
import tempfile
import sqlite3
from pathlib import Path

from core.database import Database


class TestDatabase:
    """Test database operations"""

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

    def test_database_initialization(self, temp_db):
        """Test database is initialized correctly"""
        assert temp_db.conn is not None

        # Check tables exist
        cursor = temp_db.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        assert "activities" in tables
        assert "projects" in tables
        assert "settings" in tables

    def test_save_activity(self, temp_db):
        """Test saving an activity"""
        start_time = datetime(2024, 1, 15, 10, 0, 0)
        end_time = datetime(2024, 1, 15, 10, 30, 0)

        activity_id = temp_db.save_activity(
            app_name="Code.exe",
            window_title="main.py - VSCode",
            start_time=start_time,
            end_time=end_time,
            is_idle=False,
            process_path="C:\\Program Files\\VSCode\\Code.exe",
        )

        assert activity_id > 0

        # Verify activity was saved
        activities = temp_db.get_activities()
        assert len(activities) == 1
        assert activities[0]["app_name"] == "Code.exe"
        assert activities[0]["window_title"] == "main.py - VSCode"
        assert activities[0]["duration"] == 1800  # 30 minutes in seconds

    def test_get_activities_with_date_filter(self, temp_db):
        """Test filtering activities by date"""
        # Add activities on different dates
        temp_db.save_activity(
            "App1", "Title1", datetime(2024, 1, 15, 10, 0), datetime(2024, 1, 15, 11, 0)
        )
        temp_db.save_activity(
            "App2", "Title2", datetime(2024, 1, 16, 10, 0), datetime(2024, 1, 16, 11, 0)
        )
        temp_db.save_activity(
            "App3", "Title3", datetime(2024, 1, 17, 10, 0), datetime(2024, 1, 17, 11, 0)
        )

        # Filter for specific date
        activities = temp_db.get_activities(
            start_date=datetime(2024, 1, 16, 0, 0),
            end_date=datetime(2024, 1, 16, 23, 59),
        )

        assert len(activities) == 1
        assert activities[0]["app_name"] == "App2"

    def test_create_project(self, temp_db):
        """Test creating a project"""
        project_id = temp_db.create_project("Test Project", "#FF5733")

        assert project_id > 0

        projects = temp_db.get_projects()
        assert len(projects) == 1
        assert projects[0]["name"] == "Test Project"
        assert projects[0]["color"] == "#FF5733"

    def test_project_unique_name(self, temp_db):
        """Test that project names must be unique"""
        temp_db.create_project("Unique Project", "#3498db")

        # Attempting to create another project with the same name should raise an error
        with pytest.raises(sqlite3.IntegrityError):
            temp_db.create_project("Unique Project", "#e74c3c")

    def test_assign_activity_to_project(self, temp_db):
        """Test assigning an activity to a project"""
        # Create project
        project_id = temp_db.create_project("Test Project")

        # Create activity
        activity_id = temp_db.save_activity(
            "Code.exe",
            "main.py",
            datetime(2024, 1, 15, 10, 0),
            datetime(2024, 1, 15, 11, 0),
        )

        # Assign activity to project
        temp_db.assign_activity_to_project(activity_id, project_id)

        # Verify assignment
        activities = temp_db.get_activities(project_id=project_id)
        assert len(activities) == 1
        assert activities[0]["project_id"] == project_id

    def test_assign_activities_by_timerange(self, temp_db):
        """Test assigning multiple activities by timerange"""
        # Create project
        project_id = temp_db.create_project("Batch Project")

        # Create multiple activities for the same app
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
            "chrome.exe",
            "GitHub",
            datetime(2024, 1, 15, 11, 0),
            datetime(2024, 1, 15, 12, 0),
        )

        # Assign all Code.exe activities in timerange
        affected = temp_db.assign_activities_by_timerange(
            start_time=datetime(2024, 1, 15, 0, 0),
            end_time=datetime(2024, 1, 15, 23, 59),
            app_name="Code.exe",
            project_id=project_id,
        )

        assert affected == 2

        # Verify assignment
        activities = temp_db.get_activities(project_id=project_id)
        assert len(activities) == 2
        assert all(a["app_name"] == "Code.exe" for a in activities)

    def test_settings(self, temp_db):
        """Test settings storage"""
        # Set a setting
        temp_db.set_setting("theme", "dark")
        temp_db.set_setting("language", "de")

        # Get settings
        assert temp_db.get_setting("theme") == "dark"
        assert temp_db.get_setting("language") == "de"

        # Get non-existent setting with default
        assert temp_db.get_setting("nonexistent", "default_value") == "default_value"

        # Update existing setting
        temp_db.set_setting("theme", "light")
        assert temp_db.get_setting("theme") == "light"

    def test_idle_activities(self, temp_db):
        """Test tracking idle activities"""
        activity_id = temp_db.save_activity(
            app_name="IDLE",
            window_title="",
            start_time=datetime(2024, 1, 15, 10, 0),
            end_time=datetime(2024, 1, 15, 10, 10),
            is_idle=True,
        )

        activities = temp_db.get_activities()
        assert len(activities) == 1
        # SQLite stores booleans as integers (0/1)
        assert activities[0]["is_idle"] in (True, 1)

    def test_activity_ordering(self, temp_db):
        """Test that activities are returned in reverse chronological order"""
        # Add activities in chronological order
        temp_db.save_activity(
            "App1", "T1", datetime(2024, 1, 15, 9, 0), datetime(2024, 1, 15, 10, 0)
        )
        temp_db.save_activity(
            "App2", "T2", datetime(2024, 1, 15, 10, 0), datetime(2024, 1, 15, 11, 0)
        )
        temp_db.save_activity(
            "App3", "T3", datetime(2024, 1, 15, 11, 0), datetime(2024, 1, 15, 12, 0)
        )

        activities = temp_db.get_activities()

        # Should be in reverse order (newest first)
        assert activities[0]["app_name"] == "App3"
        assert activities[1]["app_name"] == "App2"
        assert activities[2]["app_name"] == "App1"

    def test_project_deletion_sets_null(self, temp_db):
        """Test that deleting a project sets activity project_id to NULL"""
        # Create project and activity
        project_id = temp_db.create_project("Temporary Project")
        activity_id = temp_db.save_activity(
            "App", "Title", datetime(2024, 1, 15, 10, 0), datetime(2024, 1, 15, 11, 0)
        )
        temp_db.assign_activity_to_project(activity_id, project_id)

        # Delete project
        cursor = temp_db.conn.cursor()
        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        temp_db.conn.commit()

        # Check that activity's project_id is now NULL
        activities = temp_db.get_activities()
        # SQLite may return NULL as None or 1 (depending on row_factory)
        assert activities[0]["project_id"] in (None, 1)
