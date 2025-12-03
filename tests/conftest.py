"""
Pytest configuration and fixtures
"""
import sys
from pathlib import Path
import pytest
from datetime import datetime
from typing import Any

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.database_protocol import DatabaseProtocol


class MockDatabase(DatabaseProtocol):
    """Mock database implementation for testing"""

    def __init__(self):
        self.activities = []
        self.projects = []
        self.settings = {}
        self._activity_id_counter = 1
        self._project_id_counter = 1

    def save_activity(
        self,
        app_name: str,
        window_title: str,
        start_time: datetime,
        end_time: datetime,
        is_idle: bool = False,
        process_path: str | None = None,
    ) -> int:
        """Save activity and return ID"""
        activity_id = self._activity_id_counter
        self._activity_id_counter += 1

        duration = int((end_time - start_time).total_seconds())

        self.activities.append({
            "id": activity_id,
            "timestamp": start_time,
            "app_name": app_name,
            "window_title": window_title,
            "duration": duration,
            "is_idle": is_idle,
            "process_path": process_path,
            "project_id": None,
        })

        return activity_id

    def get_activities(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        project_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get activities with filters"""
        result = self.activities.copy()

        if start_date:
            result = [a for a in result if a["timestamp"] >= start_date]

        if end_date:
            result = [a for a in result if a["timestamp"] <= end_date]

        if project_id is not None:
            result = [a for a in result if a.get("project_id") == project_id]

        return sorted(result, key=lambda x: x["timestamp"], reverse=True)

    def create_project(self, name: str, color: str = "#3498db") -> int:
        """Create project and return ID"""
        project_id = self._project_id_counter
        self._project_id_counter += 1

        self.projects.append({
            "id": project_id,
            "name": name,
            "color": color,
        })

        return project_id

    def get_projects(self) -> list[dict[str, Any]]:
        """Get all projects"""
        return sorted(self.projects, key=lambda x: x["name"])

    def assign_activity_to_project(self, activity_id: int, project_id: int) -> None:
        """Assign activity to project"""
        for activity in self.activities:
            if activity["id"] == activity_id:
                activity["project_id"] = project_id
                break

    def assign_activities_by_timerange(
        self, start_time: datetime, end_time: datetime, app_name: str, project_id: int
    ) -> int:
        """Assign activities in timerange to project"""
        count = 0
        for activity in self.activities:
            if (
                activity["timestamp"] >= start_time
                and activity["timestamp"] <= end_time
                and activity["app_name"] == app_name
            ):
                activity["project_id"] = project_id
                count += 1
        return count

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        """Get setting value"""
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        """Set setting value"""
        self.settings[key] = value

    def close(self) -> None:
        """Close database (no-op for mock)"""
        pass


@pytest.fixture
def mock_db():
    """Fixture providing a mock database"""
    return MockDatabase()


@pytest.fixture
def sample_activities(mock_db):
    """Fixture providing sample activities"""
    base_time = datetime(2024, 1, 15, 9, 0, 0)

    # Add some sample activities
    mock_db.save_activity(
        app_name="Code.exe",
        window_title="main.py - VSCode",
        start_time=base_time,
        end_time=datetime(2024, 1, 15, 10, 30, 0),
        process_path="C:\\Program Files\\VSCode\\Code.exe",
    )

    mock_db.save_activity(
        app_name="chrome.exe",
        window_title="GitHub - Chrome",
        start_time=datetime(2024, 1, 15, 10, 30, 0),
        end_time=datetime(2024, 1, 15, 11, 0, 0),
        process_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    )

    mock_db.save_activity(
        app_name="Code.exe",
        window_title="test.py - VSCode",
        start_time=datetime(2024, 1, 15, 11, 0, 0),
        end_time=datetime(2024, 1, 15, 12, 0, 0),
        is_idle=False,
        process_path="C:\\Program Files\\VSCode\\Code.exe",
    )

    return mock_db


@pytest.fixture
def sample_projects(mock_db):
    """Fixture providing sample projects"""
    mock_db.create_project("Web Development", "#3498db")
    mock_db.create_project("Backend API", "#2ecc71")
    mock_db.create_project("Testing", "#e74c3c")

    return mock_db


@pytest.fixture
def temp_db_path(tmp_path):
    """Fixture providing a temporary database path"""
    return tmp_path
