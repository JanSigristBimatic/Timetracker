"""Project data model.

This module defines the Project dataclass for representing time tracking projects.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Project:
    """Represents a time tracking project.

    Projects are used to categorize and group activities for reporting
    and analysis purposes.

    Attributes:
        id: Unique identifier (database primary key)
        name: Project name (must be unique)
        color: Hex color code for UI display (e.g., "#FF5733")
        created_at: Timestamp when project was created
        last_used: Timestamp when project was last used
        description: Optional project description
    """

    id: int
    name: str
    color: str = "#3498db"
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    description: Optional[str] = None

    def __post_init__(self):
        """Validate and normalize project data after initialization."""
        # Ensure color starts with #
        if self.color and not self.color.startswith("#"):
            self.color = f"#{self.color}"

    @property
    def is_recently_used(self) -> bool:
        """Check if project was used in the last 7 days."""
        if not self.last_used:
            return False
        from datetime import timedelta
        return (datetime.now() - self.last_used) < timedelta(days=7)

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        """Create Project from dictionary (e.g., database row).

        Args:
            data: Dictionary with project data

        Returns:
            Project instance
        """
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        last_used = data.get("last_used")
        if isinstance(last_used, str):
            last_used = datetime.fromisoformat(last_used)

        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            color=data.get("color", "#3498db"),
            created_at=created_at,
            last_used=last_used,
            description=data.get("description"),
        )

    def to_dict(self) -> dict:
        """Convert Project to dictionary.

        Returns:
            Dictionary representation of the project
        """
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "description": self.description,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"Project({self.id}): {self.name}"

    def __eq__(self, other: object) -> bool:
        """Check equality based on ID."""
        if not isinstance(other, Project):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on ID for use in sets/dicts."""
        return hash(self.id)
