"""Merging of consecutive activities for timeline display.

Pure functions, extracted from the timeline widget so the merge
behaviour can be unit tested without a GUI.
"""

from datetime import timedelta
from typing import Any


def merge_activities(
    activities: list[dict[str, Any]],
    min_duration: int = 10,
    merge_gap: int = 60,
    project_merge_gap: int = 180,
) -> list[dict[str, Any]]:
    """Merge consecutive activities with intelligent filtering.

    Steps:
    1. Drop activities shorter than min_duration (noise reduction)
    2. Merge same-app activities whose gap is <= merge_gap
    3. Merge same-project activities whose gap is <= project_merge_gap

    Each merged activity carries:
    - end_time: display end of the block (end of the last segment)
    - duration: display duration in seconds including gaps
    - tracked_duration: sum of the original segment durations (no gaps)

    Args:
        activities: Activity dicts with timestamp, duration, app_name,
                    window_title, and optional project_id/is_idle keys
        min_duration: Minimum segment duration in seconds to keep
        merge_gap: Maximum gap in seconds for same-app merging
        project_merge_gap: Maximum gap in seconds for same-project merging

    Returns:
        List of merged activity dicts sorted by timestamp
    """
    filtered = [a for a in activities if a['duration'] >= min_duration]
    if not filtered:
        return []

    sorted_activities = sorted(filtered, key=lambda a: a['timestamp'])

    merged: list[dict[str, Any]] = []
    current = _start_block(sorted_activities[0])

    for activity in sorted_activities[1:]:
        activity_end = activity['timestamp'] + timedelta(seconds=activity['duration'])
        gap = (activity['timestamp'] - current['end_time']).total_seconds()

        if _should_merge(current, activity, gap, merge_gap, project_merge_gap):
            current['end_time'] = max(current['end_time'], activity_end)
            current['duration'] = int(
                (current['end_time'] - current['timestamp']).total_seconds()
            )
            current['tracked_duration'] += activity['duration']
            if activity['window_title']:
                current['window_title'] = activity['window_title']
        else:
            merged.append(current)
            current = _start_block(activity)

    merged.append(current)
    return merged


def _start_block(activity: dict[str, Any]) -> dict[str, Any]:
    """Create a new merge block from a single activity."""
    block = activity.copy()
    block['end_time'] = block['timestamp'] + timedelta(seconds=block['duration'])
    block['tracked_duration'] = block['duration']
    return block


def _should_merge(
    current: dict[str, Any],
    activity: dict[str, Any],
    gap: float,
    merge_gap: int,
    project_merge_gap: int,
) -> bool:
    """Decide whether an activity should extend the current block."""
    # Idle blocks are never merged with anything
    if current.get('is_idle', False) or activity.get('is_idle', False):
        return False

    if current['app_name'] != activity['app_name']:
        return False

    # Same project allows a larger gap
    same_project = (
        current.get('project_id') is not None
        and current.get('project_id') == activity.get('project_id')
    )
    allowed_gap = project_merge_gap if same_project else merge_gap

    return gap <= allowed_gap
