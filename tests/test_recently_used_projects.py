"""Tests for recently used projects feature"""

import pytest
from datetime import datetime, timedelta
from core.database import Database


class TestRecentlyUsedProjects:
    """Tests for recently used projects functionality"""

    @pytest.fixture
    def db(self, temp_db_path):
        """Create a temporary database for testing"""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                database = Database()
                yield database
                database.close()

    def test_recently_used_projects_empty(self, db):
        """Test that recently used projects is empty initially"""
        recent = db.get_recently_used_projects()
        assert recent == []

    def test_recently_used_projects_after_assignment(self, db):
        """Test that projects appear in recently used after assignment"""
        # Create test projects
        project1_id = db.create_project("Project 1", "#ff0000")
        project2_id = db.create_project("Project 2", "#00ff00")

        # Create test activities
        now = datetime.now()
        db.save_activity(
            app_name="TestApp",
            window_title="Test Window",
            start_time=now,
            end_time=now + timedelta(minutes=5),
        )

        # Assign to project 1
        db.assign_activities_by_timerange(
            start_time=now,
            end_time=now + timedelta(minutes=5),
            app_name="TestApp",
            project_id=project1_id,
        )

        # Check recently used
        recent = db.get_recently_used_projects()
        assert len(recent) == 1
        assert recent[0]['name'] == "Project 1"
        assert recent[0]['last_used'] is not None

        # Assign to project 2 (should appear first in recently used)
        db.assign_activities_by_timerange(
            start_time=now,
            end_time=now + timedelta(minutes=5),
            app_name="TestApp",
            project_id=project2_id,
        )

        recent = db.get_recently_used_projects()
        assert len(recent) == 2
        assert recent[0]['name'] == "Project 2"  # Most recent first
        assert recent[1]['name'] == "Project 1"

    def test_recently_used_projects_limit(self, db):
        """Test that recently used projects respects the limit"""
        # Create 15 projects
        project_names = []
        for i in range(15):
            project_name = f"Project {i:02d}"
            db.create_project(project_name, f"#{'0' * min(i, 5):0>6}")
            project_names.append(project_name)

        # Assign activities to all projects
        now = datetime.now()
        for i, project_name in enumerate(project_names):
            db.save_activity(
                app_name=f"App{i}",
                window_title=f"Window {i}",
                start_time=now + timedelta(minutes=i),
                end_time=now + timedelta(minutes=i + 1),
            )
            # Get project ID by name
            projects = db.get_projects()
            project = next(p for p in projects if p['name'] == project_name)
            db.assign_activities_by_timerange(
                start_time=now + timedelta(minutes=i),
                end_time=now + timedelta(minutes=i + 1),
                app_name=f"App{i}",
                project_id=project['id'],
            )

        # Request top 10
        recent = db.get_recently_used_projects(limit=10)
        assert len(recent) == 10

        # Should be the last 10 projects (most recent)
        recent_names = [p['name'] for p in recent]
        expected_names = project_names[-10:][::-1]  # Last 10, reversed (most recent first)
        assert recent_names == expected_names

    def test_recently_used_projects_order(self, db):
        """Test that recently used projects are ordered by last_used timestamp"""
        # Create projects
        db.create_project("Project 1", "#ff0000")
        db.create_project("Project 2", "#00ff00")
        db.create_project("Project 3", "#0000ff")

        # Get project IDs
        projects = db.get_projects()
        project1 = next(p for p in projects if p['name'] == "Project 1")
        project2 = next(p for p in projects if p['name'] == "Project 2")
        project3 = next(p for p in projects if p['name'] == "Project 3")

        # Create activities and assign in specific order
        now = datetime.now()

        # Assign to project 1
        db.save_activity(
            "App1", "Window1",
            now, now + timedelta(minutes=1)
        )
        db.assign_activities_by_timerange(
            now, now + timedelta(minutes=1),
            "App1", project1['id']
        )

        # Wait a bit and assign to project 2
        db.save_activity(
            "App2", "Window2",
            now + timedelta(minutes=2), now + timedelta(minutes=3)
        )
        db.assign_activities_by_timerange(
            now + timedelta(minutes=2), now + timedelta(minutes=3),
            "App2", project2['id']
        )

        # Wait a bit and assign to project 3
        db.save_activity(
            "App3", "Window3",
            now + timedelta(minutes=4), now + timedelta(minutes=5)
        )
        db.assign_activities_by_timerange(
            now + timedelta(minutes=4), now + timedelta(minutes=5),
            "App3", project3['id']
        )

        # Check order (should be 3, 2, 1)
        recent = db.get_recently_used_projects()
        assert len(recent) == 3
        assert recent[0]['name'] == "Project 3"
        assert recent[1]['name'] == "Project 2"
        assert recent[2]['name'] == "Project 1"

        # Reassign to project 1 (should move it to front)
        db.assign_activities_by_timerange(
            now + timedelta(minutes=6), now + timedelta(minutes=7),
            "App1", project1['id']
        )

        recent = db.get_recently_used_projects()
        assert recent[0]['name'] == "Project 1"
        assert recent[1]['name'] == "Project 3"
        assert recent[2]['name'] == "Project 2"
