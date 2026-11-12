"""Aggregation helpers for the project dashboard.

Pure functions so the dashboard numbers can be unit tested.
All functions ignore idle activities.
"""

from datetime import date, timedelta
from typing import Any, Optional

from utils.window_title_parser import extract_filename_from_title

UNASSIGNED_KEY = None

# Switch the trend from weekly to monthly buckets above this many weeks
MAX_WEEK_BUCKETS = 16


def aggregate_by_project(
    activities: list[dict[str, Any]],
) -> dict[Any, dict[str, Any]]:
    """Aggregate active time per project.

    Returns:
        Mapping project_id (or None for unassigned) to
        {'seconds': int, 'count': int, 'days': set[date]}
    """
    stats: dict[Any, dict[str, Any]] = {}

    for activity in activities:
        if activity.get('is_idle', False):
            continue

        key = activity.get('project_id')
        entry = stats.setdefault(key, {'seconds': 0, 'count': 0, 'days': set()})
        entry['seconds'] += activity['duration']
        entry['count'] += 1
        entry['days'].add(activity['timestamp'].date())

    return stats


def compute_kpis(activities: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute dashboard key figures.

    Returns:
        {'active_seconds', 'assigned_ratio' (0..1), 'days_with_data',
         'avg_seconds_per_day', 'busiest_day': (date, seconds) | None}
    """
    active_seconds = 0
    assigned_seconds = 0
    per_day: dict[date, int] = {}

    for activity in activities:
        if activity.get('is_idle', False):
            continue

        duration = activity['duration']
        active_seconds += duration
        if activity.get('project_id') is not None:
            assigned_seconds += duration

        day = activity['timestamp'].date()
        per_day[day] = per_day.get(day, 0) + duration

    busiest_day: Optional[tuple[date, int]] = None
    if per_day:
        busiest_day = max(per_day.items(), key=lambda x: x[1])

    days_with_data = len(per_day)
    return {
        'active_seconds': active_seconds,
        'assigned_ratio': (
            assigned_seconds / active_seconds if active_seconds else 0.0
        ),
        'days_with_data': days_with_data,
        'avg_seconds_per_day': (
            active_seconds / days_with_data if days_with_data else 0
        ),
        'busiest_day': busiest_day,
    }


def bucket_trend(
    activities: list[dict[str, Any]],
) -> tuple[list[str], list[dict[Any, int]], str]:
    """Bucket active time per project into week or month buckets.

    Weekly buckets are used for short ranges; longer ranges fall back
    to monthly buckets so the chart stays readable.

    Returns:
        (labels, buckets, mode) where buckets[i] maps project_id ->
        seconds for labels[i], mode is 'week' or 'month'
    """
    active = [a for a in activities if not a.get('is_idle', False)]
    if not active:
        return [], [], 'week'

    days = [a['timestamp'].date() for a in active]
    first_day, last_day = min(days), max(days)

    week_count = ((last_day - first_day).days // 7) + 1
    mode = 'week' if week_count <= MAX_WEEK_BUCKETS else 'month'

    buckets_map: dict[Any, dict[Any, int]] = {}
    for activity in active:
        day = activity['timestamp'].date()
        bucket_key = _week_key(day) if mode == 'week' else _month_key(day)

        bucket = buckets_map.setdefault(bucket_key, {})
        project_key = activity.get('project_id')
        bucket[project_key] = bucket.get(project_key, 0) + activity['duration']

    ordered_keys = _ordered_bucket_keys(first_day, last_day, mode)

    labels = [_bucket_label(key, mode) for key in ordered_keys]
    buckets = [buckets_map.get(key, {}) for key in ordered_keys]
    return labels, buckets, mode


def top_details_for_project(
    activities: list[dict[str, Any]],
    project_id: Any,
    limit: int = 10,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Top apps and top window contents for one project.

    Returns:
        (top_apps, top_contents) as lists of (name, seconds),
        sorted by time descending
    """
    app_times: dict[str, int] = {}
    content_times: dict[str, int] = {}

    for activity in activities:
        if activity.get('is_idle', False):
            continue
        if activity.get('project_id') != project_id:
            continue

        duration = activity['duration']
        app_times[activity['app_name']] = (
            app_times.get(activity['app_name'], 0) + duration
        )

        title = activity.get('window_title', '')
        content = extract_filename_from_title(title) if title else None
        if content:
            content_times[content] = content_times.get(content, 0) + duration

    top_apps = sorted(app_times.items(), key=lambda x: x[1], reverse=True)
    top_contents = sorted(content_times.items(), key=lambda x: x[1], reverse=True)
    return top_apps[:limit], top_contents[:limit]


def _week_key(day: date) -> tuple[int, int]:
    iso = day.isocalendar()
    return (iso[0], iso[1])


def _month_key(day: date) -> tuple[int, int]:
    return (day.year, day.month)


def _ordered_bucket_keys(first_day: date, last_day: date, mode: str) -> list:
    """All bucket keys from first to last day, including empty buckets."""
    keys = []

    if mode == 'week':
        # Start at the Monday of the first week
        cursor = first_day - timedelta(days=first_day.weekday())
        while cursor <= last_day:
            keys.append(_week_key(cursor))
            cursor += timedelta(days=7)
    else:
        year, month = first_day.year, first_day.month
        while (year, month) <= (last_day.year, last_day.month):
            keys.append((year, month))
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1

    return keys


MONTH_LABELS = [
    'Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun',
    'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez',
]


def _bucket_label(key: tuple[int, int], mode: str) -> str:
    if mode == 'week':
        return f"KW {key[1]}"
    return f"{MONTH_LABELS[key[1] - 1]} {str(key[0])[2:]}"
