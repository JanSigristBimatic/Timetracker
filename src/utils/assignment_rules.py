"""Rule based automatic project assignment.

Users define rules like "window title contains 'Bahnhof' -> project X".
Rules are evaluated deterministically when new activities are tracked,
before any statistical (AI) suggestion logic.
"""

import logging
import re
from typing import Any, Optional

from core.database_protocol import DatabaseProtocol

logger = logging.getLogger(__name__)

FIELD_APP = 'app'
FIELD_TITLE = 'title'
MATCH_CONTAINS = 'contains'
MATCH_REGEX = 'regex'

FIELD_LABELS = {FIELD_APP: 'Programm', FIELD_TITLE: 'Fenstertitel'}
MATCH_LABELS = {MATCH_CONTAINS: 'enthält', MATCH_REGEX: 'Regex'}


class AssignmentRulesEngine:
    """Evaluates user defined assignment rules against activities.

    Rules are cached in memory; call reload() after rules change.
    """

    def __init__(self, database: DatabaseProtocol):
        self.database = database
        self._rules: Optional[list[dict[str, Any]]] = None

    def reload(self) -> None:
        """Reload enabled rules from the database."""
        self._rules = self.database.get_project_rules(enabled_only=True)

    def match(self, app_name: str, window_title: Optional[str]) -> Optional[int]:
        """Return the project_id of the first matching rule, or None.

        Args:
            app_name: Name of the application executable
            window_title: Window title (may be None)
        """
        if self._rules is None:
            self.reload()

        title = window_title or ''

        for rule in self._rules:
            value = app_name if rule['field'] == FIELD_APP else title
            if rule_matches(rule, value):
                return rule['project_id']

        return None


def rule_matches(rule: dict[str, Any], value: str) -> bool:
    """Check whether a single rule matches the given value.

    Contains matching is case-insensitive; regex uses re.search with
    IGNORECASE. Invalid regex patterns never match (logged once per call).
    """
    pattern = rule['pattern']

    if rule['match_type'] == MATCH_REGEX:
        try:
            return re.search(pattern, value, re.IGNORECASE) is not None
        except re.error as e:
            logger.warning(f"Invalid regex in rule {rule.get('id')}: {pattern} ({e})")
            return False

    return pattern.lower() in value.lower()


def apply_rules_to_activities(
    database: DatabaseProtocol,
    activities: list[dict[str, Any]],
) -> int:
    """Apply all enabled rules to already stored, unassigned activities.

    Args:
        database: Database instance
        activities: Activity dicts (only unassigned ones are touched)

    Returns:
        Number of activities that received a project assignment
    """
    engine = AssignmentRulesEngine(database)
    engine.reload()

    assigned = 0
    for activity in activities:
        if activity.get('project_id') is not None:
            continue

        project_id = engine.match(
            activity['app_name'], activity.get('window_title', '')
        )
        if project_id is not None:
            database.assign_activity_to_project(
                activity['id'], project_id, update_last_used=False
            )
            assigned += 1

    return assigned
