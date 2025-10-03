"""
Tests for MockDatabase implementation

This ensures the mock database behaves correctly and matches the protocol
"""
import pytest
from datetime import datetime


class TestMockDatabase:
    """Test mock database implementation"""

    def test_save_and_retrieve_activity(self, mock_db):
        """Test saving and retrieving activities"""
        start_time = datetime(2024, 1, 15, 10, 0, 0)
        end_time = datetime(2024, 1, 15, 10, 30, 0)

        activity_id = mock_db.save_activity(
            app_name="Code.exe",
            window_title="main.py - VSCode",
            start_time=start_time,
            end_time=end_time,
            is_idle=False,
            process_path="C:\\Program Files\\VSCode\\Code.exe",
        )

        assert activity_id == 1

        activities = mock_db.get_activities()
        assert len(activities) == 1
        assert activities[0]["app_name"] == "Code.exe"
        assert activities[0]["duration"] == 1800  # 30 minutes

    def test_activity_id_increments(self, mock_db):
        """Test that activity IDs increment correctly"""
        id1 = mock_db.save_activity(
            "App1", "Title1", datetime(2024, 1, 15, 10, 0), datetime(2024, 1, 15, 11, 0)
        )
        id2 = mock_db.save_activity(
            "App2", "Title2", datetime(2024, 1, 15, 11, 0), datetime(2024, 1, 15, 12, 0)
        )

        assert id2 == id1 + 1

    def test_filter_by_date_range(self, mock_db):
        """Test filtering activities by date range"""
        mock_db.save_activity(
            "App1", "T1", datetime(2024, 1, 15, 10, 0), datetime(2024, 1, 15, 11, 0)
        )
        mock_db.save_activity(
            "App2", "T2", datetime(2024, 1, 16, 10, 0), datetime(2024, 1, 16, 11, 0)
        )
        mock_db.save_activity(
            "App3", "T3", datetime(2024, 1, 17, 10, 0), datetime(2024, 1, 17, 11, 0)
        )

        # Filter for Jan 16
        activities = mock_db.get_activities(
            start_date=datetime(2024, 1, 16, 0, 0), end_date=datetime(2024, 1, 16, 23, 59)
        )

        assert len(activities) == 1
        assert activities[0]["app_name"] == "App2"

    def test_filter_by_project(self, mock_db):
        """Test filtering activities by project"""
        project_id = mock_db.create_project("Test Project")

        id1 = mock_db.save_activity(
            "App1", "T1", datetime(2024, 1, 15, 10, 0), datetime(2024, 1, 15, 11, 0)
        )
        id2 = mock_db.save_activity(
            "App2", "T2", datetime(2024, 1, 15, 11, 0), datetime(2024, 1, 15, 12, 0)
        )

        mock_db.assign_activity_to_project(id1, project_id)

        # Filter by project
        activities = mock_db.get_activities(project_id=project_id)

        assert len(activities) == 1
        assert activities[0]["app_name"] == "App1"

    def test_create_and_retrieve_projects(self, mock_db):
        """Test creating and retrieving projects"""
        id1 = mock_db.create_project("Project A", "#FF5733")
        id2 = mock_db.create_project("Project B", "#3498db")

        projects = mock_db.get_projects()

        assert len(projects) == 2
        # Should be sorted by name
        assert projects[0]["name"] == "Project A"
        assert projects[1]["name"] == "Project B"

    def test_assign_activity_to_project(self, mock_db):
        """Test assigning activity to project"""
        project_id = mock_db.create_project("Test Project")
        activity_id = mock_db.save_activity(
            "App", "Title", datetime(2024, 1, 15, 10, 0), datetime(2024, 1, 15, 11, 0)
        )

        mock_db.assign_activity_to_project(activity_id, project_id)

        activities = mock_db.get_activities()
        assert activities[0]["project_id"] == project_id

    def test_assign_activities_by_timerange(self, mock_db):
        """Test batch assignment by timerange"""
        project_id = mock_db.create_project("Batch Project")

        mock_db.save_activity(
            "Code.exe",
            "file1.py",
            datetime(2024, 1, 15, 9, 0),
            datetime(2024, 1, 15, 10, 0),
        )
        mock_db.save_activity(
            "Code.exe",
            "file2.py",
            datetime(2024, 1, 15, 10, 0),
            datetime(2024, 1, 15, 11, 0),
        )
        mock_db.save_activity(
            "chrome.exe",
            "GitHub",
            datetime(2024, 1, 15, 11, 0),
            datetime(2024, 1, 15, 12, 0),
        )

        affected = mock_db.assign_activities_by_timerange(
            start_time=datetime(2024, 1, 15, 0, 0),
            end_time=datetime(2024, 1, 15, 23, 59),
            app_name="Code.exe",
            project_id=project_id,
        )

        assert affected == 2

    def test_settings_storage(self, mock_db):
        """Test settings storage and retrieval"""
        mock_db.set_setting("theme", "dark")
        mock_db.set_setting("language", "de")

        assert mock_db.get_setting("theme") == "dark"
        assert mock_db.get_setting("language") == "de"
        assert mock_db.get_setting("nonexistent", "default") == "default"

    def test_close_operation(self, mock_db):
        """Test that close operation doesn't raise errors"""
        mock_db.close()  # Should not raise

    def test_sample_activities_fixture(self, sample_activities):
        """Test the sample activities fixture"""
        activities = sample_activities.get_activities()

        assert len(activities) == 3
        # Check they're in reverse chronological order
        assert activities[0]["app_name"] == "Code.exe"
        assert activities[0]["window_title"] == "test.py - VSCode"

    def test_sample_projects_fixture(self, sample_projects):
        """Test the sample projects fixture"""
        projects = sample_projects.get_projects()

        assert len(projects) == 3
        project_names = [p["name"] for p in projects]
        assert "Web Development" in project_names
        assert "Backend API" in project_names
        assert "Testing" in project_names
