"""Activity data model.

This module defines the Activity dataclass for representing tracked activities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Activity:
    """Represents a tracked user activity.

    An activity is a period of time where the user was working with a specific
    application and window. Activities can be assigned to projects for time
    tracking purposes.

    Attributes:
        id: Unique identifier (database primary key)
        app_name: Name of the application executable (e.g., "chrome.exe")
        window_title: Title of the active window
        timestamp: Start time of the activity
        duration: Duration in seconds
        project_id: ID of assigned project (None if unassigned)
        project_name: Name of assigned project (convenience field)
        project_color: Color of assigned project (convenience field)
        is_idle: Whether this represents idle time
        process_path: Full path to the executable
        category: Optional category classification
    """

    id: int
    app_name: str
    window_title: str
    timestamp: datetime
    duration: int
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    project_color: Optional[str] = None
    is_idle: bool = False
    process_path: Optional[str] = None
    category: Optional[str] = None

    @property
    def end_time(self) -> datetime:
        """Calculate end time from timestamp and duration."""
        from datetime import timedelta
        return self.timestamp + timedelta(seconds=self.duration)

    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        return self.duration / 60.0

    @property
    def duration_hours(self) -> float:
        """Get duration in hours."""
        return self.duration / 3600.0

    @property
    def is_assigned(self) -> bool:
        """Check if activity is assigned to a project."""
        return self.project_id is not None

    @classmethod
    def from_dict(cls, data: dict) -> "Activity":
        """Create Activity from dictionary (e.g., database row).

        Args:
            data: Dictionary with activity data

        Returns:
            Activity instance
        """
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            id=data.get("id", 0),
            app_name=data.get("app_name", ""),
            window_title=data.get("window_title", ""),
            timestamp=timestamp or datetime.now(),
            duration=data.get("duration", 0),
            project_id=data.get("project_id"),
            project_name=data.get("project_name"),
            project_color=data.get("project_color"),
            is_idle=bool(data.get("is_idle", False)),
            process_path=data.get("process_path"),
            category=data.get("category"),
        )

    def to_dict(self) -> dict:
        """Convert Activity to dictionary.

        Returns:
            Dictionary representation of the activity
        """
        return {
            "id": self.id,
            "app_name": self.app_name,
            "window_title": self.window_title,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "duration": self.duration,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "project_color": self.project_color,
            "is_idle": self.is_idle,
            "process_path": self.process_path,
            "category": self.category,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        project_info = f" [{self.project_name}]" if self.project_name else ""
        return f"{self.app_name}: {self.window_title[:50]}{project_info} ({self.duration}s)"
