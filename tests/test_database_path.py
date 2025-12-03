"""
Tests for custom database path functionality
"""
import os
import pytest
import tempfile
from pathlib import Path

from core.database import Database
from utils.config import get_database_path


class TestDatabasePath:
    """Test custom database path functionality"""

    def test_default_database_path(self):
        """Test that default path is used when no custom path is set"""
        # Clear environment variable
        original_env = os.environ.get('DATABASE_PATH')
        if 'DATABASE_PATH' in os.environ:
            del os.environ['DATABASE_PATH']

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Monkey-patch Path.home
                original_home = Path.home
                Path.home = lambda: Path(tmpdir)

                db = Database()
                expected_path = str(Path(tmpdir) / '.timetracker' / 'timetracker.db')

                assert db.db_path == expected_path
                assert Path(db.db_path).exists()

                db.close()
                Path.home = original_home

        finally:
            # Restore environment
            if original_env:
                os.environ['DATABASE_PATH'] = original_env

    def test_custom_database_path_via_env(self):
        """Test that environment variable DATABASE_PATH is respected"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = str(Path(tmpdir) / 'custom' / 'my_database.db')
            os.environ['DATABASE_PATH'] = custom_path

            try:
                db = Database()

                assert db.db_path == custom_path
                assert Path(db.db_path).exists()
                assert Path(db.db_path).parent.name == 'custom'

                db.close()

            finally:
                # Clean up environment
                if 'DATABASE_PATH' in os.environ:
                    del os.environ['DATABASE_PATH']

    def test_custom_database_path_via_constructor(self):
        """Test that constructor parameter overrides environment"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = str(Path(tmpdir) / 'env' / 'env_database.db')
            constructor_path = str(Path(tmpdir) / 'constructor' / 'constructor_database.db')

            os.environ['DATABASE_PATH'] = env_path

            try:
                # Constructor parameter should take precedence
                db = Database(db_path=constructor_path)

                assert db.db_path == constructor_path
                assert Path(db.db_path).exists()
                assert Path(db.db_path).parent.name == 'constructor'

                db.close()

            finally:
                # Clean up environment
                if 'DATABASE_PATH' in os.environ:
                    del os.environ['DATABASE_PATH']

    def test_database_path_creates_parent_directory(self):
        """Test that parent directories are created automatically"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a nested path that doesn't exist yet
            nested_path = str(Path(tmpdir) / 'level1' / 'level2' / 'level3' / 'database.db')

            db = Database(db_path=nested_path)

            assert db.db_path == nested_path
            assert Path(db.db_path).exists()
            assert Path(db.db_path).parent.exists()

            db.close()

    def test_get_database_path_config_function(self):
        """Test the get_database_path config utility function"""
        # Test with environment variable
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = str(Path(tmpdir) / 'custom_db.db')
            os.environ['DATABASE_PATH'] = custom_path

            try:
                result = get_database_path()
                assert result == custom_path

            finally:
                if 'DATABASE_PATH' in os.environ:
                    del os.environ['DATABASE_PATH']

        # Test without environment variable (should return default)
        if 'DATABASE_PATH' in os.environ:
            del os.environ['DATABASE_PATH']

        result = get_database_path()
        expected_default = str(Path.home() / '.timetracker' / 'timetracker.db')
        assert result == expected_default

    def test_database_operations_with_custom_path(self):
        """Test that database operations work correctly with custom path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = str(Path(tmpdir) / 'test_operations.db')

            db = Database(db_path=custom_path)

            # Test basic operations
            project_id = db.create_project("Test Project", "#FF5733")
            assert project_id > 0

            projects = db.get_projects()
            # Should have 2 projects: "Social Media" (auto-created) and "Test Project"
            assert len(projects) == 2

            # Verify the database file is at the custom location
            assert Path(custom_path).exists()
            assert db.db_path == custom_path

            db.close()

    def test_empty_env_variable_uses_default(self):
        """Test that empty DATABASE_PATH environment variable uses default"""
        os.environ['DATABASE_PATH'] = '   '  # Whitespace only

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                original_home = Path.home
                Path.home = lambda: Path(tmpdir)

                db = Database()
                expected_path = str(Path(tmpdir) / '.timetracker' / 'timetracker.db')

                assert db.db_path == expected_path

                db.close()
                Path.home = original_home

        finally:
            if 'DATABASE_PATH' in os.environ:
                del os.environ['DATABASE_PATH']
