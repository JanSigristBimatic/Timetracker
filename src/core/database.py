import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class Database:
    def __init__(self):
        """Initialize SQLite database connection"""
        # Create database directory in user's home folder
        db_dir = Path.home() / '.timetracker'
        db_dir.mkdir(exist_ok=True)

        # Database file path
        db_path = db_dir / 'timetracker.db'

        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        self.create_tables()

    def create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.conn.cursor()

        # Projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Activities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                app_name TEXT NOT NULL,
                window_title TEXT,
                duration INTEGER NOT NULL,
                category TEXT,
                project_id INTEGER,
                is_idle BOOLEAN DEFAULT 0,
                process_path TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
            )
        ''')

        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Create indexes for better performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_activities_timestamp
            ON activities(timestamp)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_activities_project
            ON activities(project_id)
        ''')

        self.conn.commit()
        cursor.close()

    def save_activity(
        self,
        app_name: str,
        window_title: str,
        start_time: datetime,
        end_time: datetime,
        is_idle: bool = False,
        process_path: Optional[str] = None,
    ) -> int:
        """Save a tracked activity to the database"""
        duration = int((end_time - start_time).total_seconds())

        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO activities (timestamp, app_name, window_title, duration, is_idle, process_path)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (start_time, app_name, window_title, duration, is_idle, process_path))

        activity_id = cursor.lastrowid
        self.conn.commit()
        cursor.close()

        return int(activity_id) if activity_id else 0

    def get_activities(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        project_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Retrieve activities with optional filters"""
        cursor = self.conn.cursor()

        query = 'SELECT * FROM activities WHERE 1=1'
        params = []

        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)

        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date)

        if project_id:
            query += ' AND project_id = ?'
            params.append(project_id)

        query += ' ORDER BY timestamp DESC'

        cursor.execute(query, params)
        activities = []

        for row in cursor.fetchall():
            activity = dict(row)
            # Convert timestamp string to datetime object
            if isinstance(activity['timestamp'], str):
                activity['timestamp'] = datetime.fromisoformat(activity['timestamp'])
            activities.append(activity)

        cursor.close()

        return activities

    def create_project(self, name: str, color: str = "#3498db") -> int:
        """Create a new project"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO projects (name, color)
            VALUES (?, ?)
        ''', (name, color))

        project_id = cursor.lastrowid
        self.conn.commit()
        cursor.close()

        return int(project_id) if project_id else 0

    def get_projects(self) -> list[dict[str, Any]]:
        """Get all projects"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM projects ORDER BY name')
        projects = [dict(row) for row in cursor.fetchall()]
        cursor.close()

        return projects

    def assign_activity_to_project(self, activity_id: int, project_id: int) -> None:
        """Assign an activity to a project"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE activities
            SET project_id = ?
            WHERE id = ?
        ''', (project_id, activity_id))

        self.conn.commit()
        cursor.close()

    def assign_activities_by_timerange(
        self, start_time: datetime, end_time: datetime, app_name: str, project_id: int
    ) -> int:
        """Assign all activities in a time range for a specific app to a project"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE activities
            SET project_id = ?
            WHERE timestamp >= ?
              AND timestamp <= ?
              AND app_name = ?
        ''', (project_id, start_time, end_time, app_name))

        rows_affected = cursor.rowcount
        self.conn.commit()
        cursor.close()

        return rows_affected

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a setting value"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        cursor.close()

        return result[0] if result else default

    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        ''', (key, value))

        self.conn.commit()
        cursor.close()

    def close(self) -> None:
        """Close database connection"""
        if self.conn:
            self.conn.close()
