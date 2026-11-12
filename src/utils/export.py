"""Export functionality for time tracking data"""
import csv
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from core.database_protocol import DatabaseProtocol
from utils.project_stats import aggregate_by_project

UNASSIGNED_LABEL = 'Nicht zugeordnet'

# utf-8-sig writes a BOM so Excel shows umlauts correctly
CSV_ENCODING = 'utf-8-sig'


class Exporter:
    """Handle data exports"""

    def __init__(self, database: DatabaseProtocol):
        self.database = database

    def export_csv(self, start_date: datetime, end_date: datetime, filepath: str) -> int:
        """Export activities to CSV file"""
        activities = self._load_activities(start_date, end_date)
        rows = activity_rows(activities, self._project_names())
        _write_csv(filepath, rows)
        return len(activities)

    def export_project_summary_csv(
        self, start_date: datetime, end_date: datetime, filepath: str
    ) -> int:
        """Export project summary to CSV"""
        activities = self._load_activities(start_date, end_date)
        rows = project_summary_rows(activities, self._project_names())
        _write_csv(filepath, rows)
        return len(rows)

    def export_excel(self, start_date: datetime, end_date: datetime, filepath: str) -> int:
        """Export activities to an Excel file with one sheet per view"""
        activities = self._load_activities(start_date, end_date)
        project_names = self._project_names()

        sheets = {
            'Detailliert': activity_rows(activities, project_names),
            'Projekt-Zusammenfassung': project_summary_rows(activities, project_names),
            'Tag x Projekt': day_project_rows(activities, project_names),
            'Tages-Zusammenfassung': daily_summary_rows(activities),
        }

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for sheet_name, rows in sheets.items():
                if rows:
                    pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False)

            for worksheet in writer.sheets.values():
                _fit_column_widths(worksheet)

        return len(activities)

    def _load_activities(self, start_date: datetime, end_date: datetime) -> list[dict]:
        activities = self.database.get_activities(start_date=start_date, end_date=end_date)
        return sorted(activities, key=lambda a: a['timestamp'])

    def _project_names(self) -> dict[int, str]:
        return {p['id']: p['name'] for p in self.database.get_projects()}


def activity_rows(
    activities: list[dict[str, Any]], project_names: dict[int, str]
) -> list[dict[str, Any]]:
    """One row per stored activity, including idle periods."""
    rows = []
    for activity in activities:
        timestamp = activity['timestamp']
        end_time = timestamp + timedelta(seconds=activity['duration'])
        rows.append({
            'Datum': timestamp.strftime('%Y-%m-%d'),
            'Startzeit': timestamp.strftime('%H:%M:%S'),
            'Endzeit': end_time.strftime('%H:%M:%S'),
            'Dauer (Minuten)': round(activity['duration'] / 60, 2),
            'Programm': activity['app_name'],
            'Fenster-Titel': activity.get('window_title') or '',
            'Projekt': _assigned_project_name(activity, project_names),
            'Idle': 'Ja' if activity.get('is_idle') else 'Nein',
        })
    return rows


def project_summary_rows(
    activities: list[dict[str, Any]], project_names: dict[int, str]
) -> list[dict[str, Any]]:
    """Active time per project, sorted by project name."""
    rows = []
    for project_id, stats in aggregate_by_project(activities).items():
        rows.append({
            'Projekt': _project_label(project_id, project_names),
            'Gesamtzeit (Stunden)': round(stats['seconds'] / 3600, 2),
            'Gesamtzeit (Minuten)': round(stats['seconds'] / 60, 2),
            'Anzahl Aktivitäten': stats['count'],
        })
    return sorted(rows, key=lambda r: r['Projekt'])


def day_project_rows(
    activities: list[dict[str, Any]], project_names: dict[int, str]
) -> list[dict[str, Any]]:
    """Active hours per day and project, the basis for a time report."""
    seconds: dict[tuple[str, str], int] = {}
    for activity in activities:
        if activity.get('is_idle'):
            continue
        key = (
            activity['timestamp'].strftime('%Y-%m-%d'),
            _project_label(activity.get('project_id'), project_names),
        )
        seconds[key] = seconds.get(key, 0) + activity['duration']

    return [
        {'Datum': day, 'Projekt': project, 'Stunden': round(total / 3600, 2)}
        for (day, project), total in sorted(seconds.items())
    ]


def daily_summary_rows(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Active and idle time per day."""
    days: dict[str, dict[str, int]] = {}
    for activity in activities:
        day = days.setdefault(
            activity['timestamp'].strftime('%Y-%m-%d'),
            {'active': 0, 'idle': 0, 'count': 0},
        )
        day['idle' if activity.get('is_idle') else 'active'] += activity['duration']
        day['count'] += 1

    return [
        {
            'Datum': day,
            'Gesamtzeit (Stunden)': round((stats['active'] + stats['idle']) / 3600, 2),
            'Aktive Zeit (Stunden)': round(stats['active'] / 3600, 2),
            'Idle Zeit (Stunden)': round(stats['idle'] / 3600, 2),
            'Anzahl Aktivitäten': stats['count'],
        }
        for day, stats in sorted(days.items())
    ]


def _assigned_project_name(activity: dict[str, Any], project_names: dict[int, str]) -> str:
    project_id = activity.get('project_id')
    return project_names.get(project_id, '') if project_id is not None else ''


def _project_label(project_id: Any, project_names: dict[int, str]) -> str:
    return project_names.get(project_id, UNASSIGNED_LABEL)


def _write_csv(filepath: str, rows: list[dict[str, Any]]) -> None:
    with open(filepath, 'w', newline='', encoding=CSV_ENCODING) as csvfile:
        if not rows:
            return
        writer = csv.DictWriter(csvfile, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _fit_column_widths(worksheet) -> None:
    for column in worksheet.columns:
        longest = max(len(str(cell.value)) for cell in column if cell.value is not None)
        worksheet.column_dimensions[column[0].column_letter].width = min(longest + 2, 50)
