"""Export functionality for time tracking data"""
import csv
from datetime import datetime, timedelta
from pathlib import Path


class Exporter:
    """Handle data exports"""

    def __init__(self, database):
        self.database = database

    def export_csv(self, start_date, end_date, filepath):
        """Export activities to CSV file"""
        activities = self.database.get_activities(
            start_date=start_date,
            end_date=end_date
        )

        # Get project mapping
        projects = {p['id']: p['name'] for p in self.database.get_projects()}

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Datum',
                'Startzeit',
                'Endzeit',
                'Dauer (Minuten)',
                'Programm',
                'Fenster-Titel',
                'Projekt',
                'Idle'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()

            for activity in activities:
                timestamp = activity['timestamp']
                duration_minutes = round(activity['duration'] / 60, 2)
                end_time = timestamp + datetime.timedelta(seconds=activity['duration'])

                project_name = ''
                if activity.get('project_id'):
                    project_name = projects.get(activity['project_id'], '')

                writer.writerow({
                    'Datum': timestamp.strftime('%Y-%m-%d'),
                    'Startzeit': timestamp.strftime('%H:%M:%S'),
                    'Endzeit': end_time.strftime('%H:%M:%S'),
                    'Dauer (Minuten)': duration_minutes,
                    'Programm': activity['app_name'],
                    'Fenster-Titel': activity.get('window_title', ''),
                    'Projekt': project_name,
                    'Idle': 'Ja' if activity.get('is_idle') else 'Nein'
                })

        return len(activities)

    def export_project_summary_csv(self, start_date, end_date, filepath):
        """Export project summary to CSV"""
        activities = self.database.get_activities(
            start_date=start_date,
            end_date=end_date
        )

        # Get projects
        projects_dict = {p['id']: p['name'] for p in self.database.get_projects()}

        # Aggregate by project
        project_stats = {}

        for activity in activities:
            if activity.get('is_idle'):
                continue

            project_id = activity.get('project_id')
            project_name = projects_dict.get(project_id, 'Nicht zugeordnet')

            if project_name not in project_stats:
                project_stats[project_name] = {
                    'total_seconds': 0,
                    'activity_count': 0
                }

            project_stats[project_name]['total_seconds'] += activity['duration']
            project_stats[project_name]['activity_count'] += 1

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Projekt',
                'Gesamtzeit (Stunden)',
                'Gesamtzeit (Minuten)',
                'Anzahl Aktivitäten'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()

            for project_name, stats in sorted(project_stats.items()):
                total_hours = round(stats['total_seconds'] / 3600, 2)
                total_minutes = round(stats['total_seconds'] / 60, 2)

                writer.writerow({
                    'Projekt': project_name,
                    'Gesamtzeit (Stunden)': total_hours,
                    'Gesamtzeit (Minuten)': total_minutes,
                    'Anzahl Aktivitäten': stats['activity_count']
                })

        return len(project_stats)
