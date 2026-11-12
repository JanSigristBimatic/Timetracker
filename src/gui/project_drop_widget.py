"""Drop target widget for assigning activities to a project via drag & drop."""

import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Optional

from PyQt6.QtWidgets import QWidget

from core.database_protocol import DatabaseProtocol

from .theme import get_theme

logger = logging.getLogger(__name__)


class ProjectDropWidget(QWidget):
    """Widget that accepts activity drops for project assignment.

    Args:
        database: Database instance
        project_id: Target project ID
        project_name: Target project name (for logging)
        on_assigned: Callback receiving the undo record
            {'type': 'assign', 'changes': [(activity_id, old_project_id), ...]}
            called after a successful drop
    """

    def __init__(
        self,
        database: DatabaseProtocol,
        project_id: int,
        project_name: str,
        on_assigned: Optional[Callable[[dict], None]] = None,
    ):
        super().__init__()
        self.database = database
        self.project_id = project_id
        self.project_name = project_name
        self.on_assigned = on_assigned
        self.theme = get_theme()
        self.setAcceptDrops(True)
        self.original_stylesheet = ""

    def dragEnterEvent(self, event):
        """Accept drag events with activity data"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.original_stylesheet = self.styleSheet()
            accent = self.theme.colors.accent
            highlight = self.theme.colors.background_tertiary
            self.setStyleSheet(
                self.original_stylesheet +
                f"border: 2px dashed {accent}; background-color: {highlight};"
            )

    def dragLeaveEvent(self, event):
        """Reset style when drag leaves"""
        self.setStyleSheet(self.original_stylesheet)

    def dropEvent(self, event):
        """Handle drop of activities"""
        self.setStyleSheet(self.original_stylesheet)
        if not event.mimeData().hasText():
            return

        try:
            activity_data = json.loads(event.mimeData().text())

            changes: list[tuple[int, Optional[int]]] = []
            total_count = 0

            for act_data in activity_data:
                timestamp = datetime.fromisoformat(act_data['timestamp'])
                end_time = timestamp + timedelta(seconds=act_data['duration'])
                app_name = act_data['app_name']

                # Capture previous assignments for undo
                affected = self.database.get_activities_in_timerange(
                    timestamp, end_time, app_name
                )
                changes.extend(
                    (a['id'], a.get('project_id')) for a in affected
                )

                total_count += self.database.assign_activities_by_timerange(
                    timestamp, end_time, app_name, self.project_id
                )

            logger.info(
                f"Assigned {total_count} activities to project '{self.project_name}'"
            )

            if self.on_assigned:
                self.on_assigned({'type': 'assign', 'changes': changes})

            event.acceptProposedAction()

        except Exception as e:
            logger.error(f"Error dropping activities: {e}", exc_info=True)
