"""Export functionality for time tracking data"""
import csv
from datetime import datetime, timedelta

import pandas as pd

from core.database_protocol import DatabaseProtocol


class Exporter:
    """Handle data exports"""

    def __init__(self, database: DatabaseProtocol):
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
                end_time = timestamp + timedelta(seconds=activity['duration'])

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

    def export_excel(self, start_date, end_date, filepath):
        """Export activities to Excel file with multiple sheets"""
        activities = self.database.get_activities(
            start_date=start_date,
            end_date=end_date
        )

        # Get project mapping
        projects_dict = {p['id']: p['name'] for p in self.database.get_projects()}

        # Prepare detailed data
        detailed_data = []
        for activity in activities:
            timestamp = activity['timestamp']
            duration_minutes = round(activity['duration'] / 60, 2)
            duration_hours = round(activity['duration'] / 3600, 2)
            end_time = timestamp + timedelta(seconds=activity['duration'])

            project_name = ''
            if activity.get('project_id'):
                project_name = projects_dict.get(activity['project_id'], '')

            detailed_data.append({
                'Datum': timestamp.strftime('%Y-%m-%d'),
                'Startzeit': timestamp.strftime('%H:%M:%S'),
                'Endzeit': end_time.strftime('%H:%M:%S'),
                'Dauer (Minuten)': duration_minutes,
                'Dauer (Stunden)': duration_hours,
                'Programm': activity['app_name'],
                'Fenster-Titel': activity.get('window_title', ''),
                'Projekt': project_name,
                'Idle': 'Ja' if activity.get('is_idle') else 'Nein'
            })

        # Prepare project summary
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

        summary_data = []
        for project_name, stats in sorted(project_stats.items()):
            summary_data.append({
                'Projekt': project_name,
                'Gesamtzeit (Stunden)': round(stats['total_seconds'] / 3600, 2),
                'Gesamtzeit (Minuten)': round(stats['total_seconds'] / 60, 2),
                'Anzahl Aktivitäten': stats['activity_count']
            })

        # Prepare daily summary
        daily_stats = {}
        for activity in activities:
            date_str = activity['timestamp'].strftime('%Y-%m-%d')

            if date_str not in daily_stats:
                daily_stats[date_str] = {
                    'total_seconds': 0,
                    'active_seconds': 0,
                    'idle_seconds': 0,
                    'activity_count': 0
                }

            daily_stats[date_str]['total_seconds'] += activity['duration']
            daily_stats[date_str]['activity_count'] += 1

            if activity.get('is_idle'):
                daily_stats[date_str]['idle_seconds'] += activity['duration']
            else:
                daily_stats[date_str]['active_seconds'] += activity['duration']

        daily_data = []
        for date_str, stats in sorted(daily_stats.items()):
            daily_data.append({
                'Datum': date_str,
                'Gesamtzeit (Stunden)': round(stats['total_seconds'] / 3600, 2),
                'Aktive Zeit (Stunden)': round(stats['active_seconds'] / 3600, 2),
                'Idle Zeit (Stunden)': round(stats['idle_seconds'] / 3600, 2),
                'Anzahl Aktivitäten': stats['activity_count']
            })

        # Create Excel file with multiple sheets
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Detailed activities sheet
            if detailed_data:
                df_detailed = pd.DataFrame(detailed_data)
                df_detailed.to_excel(writer, sheet_name='Detailliert', index=False)

            # Project summary sheet
            if summary_data:
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='Projekt-Zusammenfassung', index=False)

            # Daily summary sheet
            if daily_data:
                df_daily = pd.DataFrame(daily_data)
                df_daily.to_excel(writer, sheet_name='Tages-Zusammenfassung', index=False)

            # Adjust column widths
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

        return len(activities)
