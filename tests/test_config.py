"""
Tests for configuration and utility functions
"""
import pytest
import os
from unittest.mock import patch

from utils.config import (
    should_ignore_activity,
    get_ignored_processes,
    get_ignored_window_titles,
    DEFAULT_IGNORED_PROCESSES,
    DEFAULT_IGNORED_WINDOW_TITLES,
)


class TestConfig:
    """Test configuration functions"""

    def test_default_ignored_processes(self):
        """Test default ignored processes are loaded"""
        processes = get_ignored_processes()

        assert "explorer.exe" in processes
        assert "python.exe" in processes
        assert len(processes) > 0

    def test_default_ignored_window_titles(self):
        """Test default ignored window titles are loaded"""
        titles = get_ignored_window_titles()

        assert "" in titles
        assert "Program Manager" in titles

    def test_should_ignore_process(self):
        """Test that ignored processes are detected"""
        assert should_ignore_activity("explorer.exe", "Windows Explorer")
        assert should_ignore_activity("python.exe", "Python")
        assert should_ignore_activity("dwm.exe", "Desktop Window Manager")

    def test_should_ignore_window_title(self):
        """Test that ignored window titles are detected"""
        assert should_ignore_activity("some_app.exe", "")
        assert should_ignore_activity("some_app.exe", "Program Manager")

    def test_should_not_ignore_valid_activity(self):
        """Test that valid activities are not ignored"""
        assert not should_ignore_activity("Code.exe", "main.py - VSCode")
        assert not should_ignore_activity("chrome.exe", "GitHub - Chrome")

    def test_case_insensitive_process_matching(self):
        """Test that process matching is case-insensitive"""
        assert should_ignore_activity("EXPLORER.EXE", "")
        assert should_ignore_activity("Explorer.exe", "")
        assert should_ignore_activity("python.EXE", "")

    @patch.dict(os.environ, {"IGNORED_PROCESSES": "custom.exe,another.exe"})
    def test_custom_ignored_processes_from_env(self):
        """Test loading custom ignored processes from environment"""
        processes = get_ignored_processes()

        assert "custom.exe" in processes
        assert "another.exe" in processes

    @patch.dict(os.environ, {"IGNORED_WINDOW_TITLES": "Secret Window,Private"})
    def test_custom_ignored_titles_from_env(self):
        """Test loading custom ignored window titles from environment"""
        titles = get_ignored_window_titles()

        assert "Secret Window" in titles
        assert "Private" in titles

    @patch.dict(os.environ, {"IGNORED_PROCESSES": "  test.exe  ,  other.exe  "})
    def test_env_values_are_trimmed(self):
        """Test that environment values are trimmed"""
        processes = get_ignored_processes()

        assert "test.exe" in processes
        assert "other.exe" in processes
        # Should not have whitespace
        assert "  test.exe  " not in processes

    @patch.dict(os.environ, {"IGNORED_PROCESSES": ""})
    def test_empty_env_uses_defaults(self):
        """Test that empty environment variable uses defaults"""
        processes = get_ignored_processes()

        # Should use defaults
        assert "explorer.exe" in processes

    def test_ignore_activity_respects_env(self):
        """Test that should_ignore_activity respects environment variables"""
        with patch.dict(os.environ, {"IGNORED_PROCESSES": "mycustomapp.exe"}):
            assert should_ignore_activity("mycustomapp.exe", "Title")
            # When custom env is set, defaults are replaced (not merged)
            assert not should_ignore_activity("explorer.exe", "Title")
