"""
Database Protocol (Boundary Interface)

This module defines the protocol (interface) for database operations,
following Uncle Bob's Clean Architecture principles.
The protocol defines the boundary between the application logic and the database implementation.
"""

from datetime import datetime
from typing import Any, Optional, Protocol


class DatabaseProtocol(Protocol):
    """Protocol defining the database boundary interface"""

    def save_activity(
        self,
        app_name: str,
        window_title: str,
        start_time: datetime,
        end_time: datetime,
        is_idle: bool = False,
        process_path: Optional[str] = None,
    ) -> int:
        """
        Save a tracked activity to the database

        Args:
            app_name: Name of the application
            window_title: Title of the window
            start_time: Start time of the activity
            end_time: End time of the activity
            is_idle: Whether the activity represents idle time
            process_path: Optional path to the process executable

        Returns:
            The ID of the saved activity
        """
        ...

    def get_activities(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        project_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve activities with optional filters

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            project_id: Optional project ID filter

        Returns:
            List of activity dictionaries
        """
        ...

    def create_project(self, name: str, color: str = "#3498db") -> int:
        """
        Create a new project

        Args:
            name: Project name
            color: Project color (hex format)

        Returns:
            The ID of the created project
        """
        ...

    def get_projects(self) -> list[dict[str, Any]]:
        """
        Get all projects

        Returns:
            List of project dictionaries
        """
        ...

    def assign_activity_to_project(self, activity_id: int, project_id: int) -> None:
        """
        Assign an activity to a project

        Args:
            activity_id: ID of the activity
            project_id: ID of the project
        """
        ...

    def assign_activities_by_timerange(
        self,
        start_time: datetime,
        end_time: datetime,
        app_name: str,
        project_id: int,
    ) -> int:
        """
        Assign all activities in a time range for a specific app to a project

        Args:
            start_time: Start of the time range
            end_time: End of the time range
            app_name: Name of the application
            project_id: ID of the project

        Returns:
            Number of activities affected
        """
        ...

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a setting value

        Args:
            key: Setting key
            default: Default value if setting not found

        Returns:
            Setting value or default
        """
        ...

    def set_setting(self, key: str, value: str) -> None:
        """
        Set a setting value

        Args:
            key: Setting key
            value: Setting value
        """
        ...

    def get_social_media_project_id(self) -> Optional[int]:
        """
        Get the ID of the Social Media project

        Returns:
            The ID of the Social Media project or None if it doesn't exist
        """
        ...

    def get_recently_used_projects(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recently used projects

        Args:
            limit: Maximum number of projects to return (default: 10)

        Returns:
            List of recently used project dictionaries
        """
        ...

    def delete_activities_by_timerange(
        self,
        start_time: datetime,
        end_time: datetime,
        app_name: str,
    ) -> int:
        """
        Delete all activities in a time range for a specific app

        Args:
            start_time: Start of the time range
            end_time: End of the time range
            app_name: Name of the application

        Returns:
            Number of activities deleted
        """
        ...

    def close(self) -> None:
        """Close database connection"""
        ...
