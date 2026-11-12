import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Optional

from utils.config import get_database_path

# SQLite-compatible datetime format (space separator, not 'T', with microseconds)
_SQLITE_DT_FMT = '%Y-%m-%d %H:%M:%S.%f'

# Durations are stored as whole seconds; rounding lets neighbours overlap
# by up to half a second, which must not count as a real overlap.
OVERLAP_TOLERANCE_SECONDS = 0.5

SOCIAL_MEDIA_MIGRATION_KEY = 'migration_social_media_rules'

# (field, match_type, pattern) seeded once for an existing Social Media project
SOCIAL_MEDIA_RULES = [
    *[('title', 'contains', keyword) for keyword in (
        'facebook', 'twitter', 'instagram', 'linkedin', 'reddit', 'tiktok',
        'youtube', 'snapchat', 'pinterest', 'whatsapp', 'telegram',
        'discord', 'twitch',
    )],
    ('title', 'regex', r'(^|[^\w.-])x\.com'),
    *[('app', 'contains', app) for app in ('discord', 'telegram', 'whatsapp')],
]

# Lower bound for the overlap search so it can use the timestamp index.
# No single activity lasts longer than this.
OVERLAP_LOOKBACK = timedelta(days=7)


def _seconds_between(start: datetime, end: datetime) -> int:
    """Whole seconds between two datetimes, rounded (never truncated).

    Truncating would lose half a second per activity on average, which
    adds up to minutes per day with hundreds of window switches.
    """
    return max(0, round((end - start).total_seconds()))


def _as_datetime(value: Any) -> datetime:
    return datetime.fromisoformat(value) if isinstance(value, str) else value

# Register adapters/converters for datetime (required since Python 3.12)
sqlite3.register_adapter(datetime, lambda dt: dt.strftime(_SQLITE_DT_FMT))
sqlite3.register_converter("TIMESTAMP", lambda b: datetime.fromisoformat(b.decode()))


class Database:
    def __init__(self, db_path: Optional[str] = None):
        """Initialize SQLite database connection

        Args:
            db_path: Optional custom database path. If None, uses default location
                    or DATABASE_PATH environment variable.
        """
        final_db_path = Path(db_path or get_database_path())
        final_db_path.parent.mkdir(parents=True, exist_ok=True)

        # Store the path for reference
        self.db_path = str(final_db_path)

        self.conn = sqlite3.connect(
            str(final_db_path),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries

        # Enable foreign key constraints (must be done for each connection)
        self.conn.execute("PRAGMA foreign_keys = ON")

        # Thread safety lock for write operations
        self._write_lock = Lock()

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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP
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

        # Assignment rules table (deterministic auto-assignment)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                field TEXT NOT NULL,
                match_type TEXT NOT NULL DEFAULT 'contains',
                pattern TEXT NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                priority INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
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

        # Create unique index to prevent duplicate activities
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_activity
            ON activities(timestamp, app_name, window_title, duration)
        ''')

        self.conn.commit()
        cursor.close()

        # Run migrations
        self._run_migrations()

    def _run_migrations(self):
        """Run database migrations"""
        cursor = self.conn.cursor()

        # Migration: Add last_used column to projects table if it doesn't exist
        cursor.execute("PRAGMA table_info(projects)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'last_used' not in columns:
            with self._write_lock:
                cursor.execute('''
                    ALTER TABLE projects ADD COLUMN last_used TIMESTAMP
                ''')
                self.conn.commit()

        cursor.close()

        self._migrate_social_media_detector_to_rules()

    def _migrate_social_media_detector_to_rules(self) -> None:
        """Replace the former hard-coded social media detector by rules.

        Runs once. If a 'Social Media' project exists, the detector's
        keywords become ordinary rules the user can edit or delete in the
        rules dialog. Existing rules keep precedence (lower id). The former
        substring 'x.com' also matched wix.com or netflix.com, so it
        becomes a regex that requires x.com to start a domain.
        """
        if self.get_setting(SOCIAL_MEDIA_MIGRATION_KEY):
            return

        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM projects WHERE name = ?', ('Social Media',))
        row = cursor.fetchone()
        cursor.close()

        if row:
            for field, match_type, pattern in SOCIAL_MEDIA_RULES:
                self.create_project_rule(row[0], field, pattern, match_type)

        self.set_setting(SOCIAL_MEDIA_MIGRATION_KEY, '1')

    def save_activity(
        self,
        app_name: str,
        window_title: str,
        start_time: datetime,
        end_time: datetime,
        is_idle: bool = False,
        process_path: Optional[str] = None,
    ) -> int:
        """Save an activity; it replaces whatever overlaps its time range.

        Existing activities are cut around the new range: the part before
        it is kept, the part after it becomes its own row (same app, title
        and project), and fully covered rows are removed. This keeps every
        second of the day in exactly one activity.
        """
        duration = _seconds_between(start_time, end_time)

        with self._write_lock:
            cursor = self.conn.cursor()
            try:
                self._cut_overlapping_activities(cursor, start_time, end_time)

                # Insert new activity
                cursor.execute('''
                    INSERT INTO activities (timestamp, app_name, window_title, duration, is_idle, process_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (start_time.strftime(_SQLITE_DT_FMT), app_name, window_title, duration, is_idle, process_path))

                activity_id = cursor.lastrowid
                self.conn.commit()
                cursor.close()

                return int(activity_id) if activity_id else 0

            except sqlite3.IntegrityError:
                # Duplicate activity: undo the cuts made for it
                self.conn.rollback()
                cursor.close()
                return 0

    def _cut_overlapping_activities(
        self, cursor, start_time: datetime, end_time: datetime
    ) -> None:
        """Remove the range [start_time, end_time) from existing activities.

        Must be called with _write_lock held, inside the caller's
        transaction. Overlaps up to OVERLAP_TOLERANCE_SECONDS are rounding
        noise between consecutive activities and are left untouched.
        """
        cursor.execute('''
            SELECT * FROM activities
            WHERE timestamp >= ? AND timestamp < ?
              AND (julianday(timestamp) - julianday(?)) * 86400 + duration > ?
        ''', (
            (start_time - OVERLAP_LOOKBACK).strftime(_SQLITE_DT_FMT),
            end_time.strftime(_SQLITE_DT_FMT),
            start_time.strftime(_SQLITE_DT_FMT),
            OVERLAP_TOLERANCE_SECONDS,
        ))

        for row in cursor.fetchall():
            existing = dict(row)
            existing_start = _as_datetime(existing['timestamp'])
            existing_end = existing_start + timedelta(seconds=existing['duration'])

            seconds_before = _seconds_between(existing_start, start_time)
            seconds_after = _seconds_between(end_time, existing_end)

            if seconds_before > 0:
                cursor.execute(
                    'UPDATE activities SET duration = ? WHERE id = ?',
                    (seconds_before, existing['id']),
                )
                if seconds_after > 0:
                    self._insert_remainder(cursor, existing, end_time, seconds_after)
            elif seconds_after > 0:
                cursor.execute(
                    'UPDATE activities SET timestamp = ?, duration = ? WHERE id = ?',
                    (end_time.strftime(_SQLITE_DT_FMT), seconds_after, existing['id']),
                )
            else:
                cursor.execute('DELETE FROM activities WHERE id = ?', (existing['id'],))

    @staticmethod
    def _insert_remainder(
        cursor, existing: dict[str, Any], start_time: datetime, duration: int
    ) -> None:
        """Insert the tail of a split activity, keeping its attributes."""
        cursor.execute('''
            INSERT INTO activities
                (timestamp, app_name, window_title, duration,
                 category, project_id, is_idle, process_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            start_time.strftime(_SQLITE_DT_FMT),
            existing['app_name'],
            existing['window_title'],
            duration,
            existing['category'],
            existing['project_id'],
            existing['is_idle'],
            existing['process_path'],
        ))

    def get_activities(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        project_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Retrieve activities with optional filters"""
        cursor = self.conn.cursor()

        query = 'SELECT * FROM activities WHERE 1=1'
        params: list = []

        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date.strftime(_SQLITE_DT_FMT))

        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date.strftime(_SQLITE_DT_FMT))

        if project_id is not None:
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
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO projects (name, color)
                VALUES (?, ?)
            ''', (name, color))

            project_id = cursor.lastrowid
            self.conn.commit()
            cursor.close()

        return int(project_id) if project_id else 0

    def update_project(self, project_id: int, name: str, color: str) -> None:
        """Rename and/or recolor a project"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute(
                'UPDATE projects SET name = ?, color = ? WHERE id = ?',
                (name, color, project_id),
            )
            self.conn.commit()
            cursor.close()

    def delete_project(self, project_id: int) -> None:
        """Delete a project by ID"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
            self.conn.commit()
            cursor.close()

    def get_projects(self) -> list[dict[str, Any]]:
        """Get all projects"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM projects ORDER BY name')
        projects = [dict(row) for row in cursor.fetchall()]
        cursor.close()

        return projects

    def _touch_project_last_used(self, cursor, project_id: Optional[int]) -> None:
        """Update the last_used timestamp of a project.

        Must be called with _write_lock held.
        """
        if project_id is None:
            return

        cursor.execute('''
            UPDATE projects
            SET last_used = ?
            WHERE id = ?
        ''', (datetime.now().strftime(_SQLITE_DT_FMT), project_id))

    def assign_activity_to_project(
        self, activity_id: int, project_id: Optional[int], update_last_used: bool = True
    ) -> None:
        """Assign an activity to a project (None clears the assignment).

        Args:
            update_last_used: Set False for automatic background
                assignments that should not appear in "recently used".
        """
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE activities
                SET project_id = ?
                WHERE id = ?
            ''', (project_id, activity_id))

            if update_last_used:
                self._touch_project_last_used(cursor, project_id)

            self.conn.commit()
            cursor.close()

    def assign_activities_by_timerange(
        self, start_time: datetime, end_time: datetime, app_name: str, project_id: int
    ) -> int:
        """Assign all activities in a time range for a specific app to a project"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE activities
                SET project_id = ?
                WHERE timestamp >= ?
                  AND timestamp < ?
                  AND app_name = ?
            ''', (project_id, start_time.strftime(_SQLITE_DT_FMT), end_time.strftime(_SQLITE_DT_FMT), app_name))

            rows_affected = cursor.rowcount
            self._touch_project_last_used(cursor, project_id)
            self.conn.commit()
            cursor.close()

        return rows_affected

    def get_recently_used_projects(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recently used projects"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, name, color, last_used
            FROM projects
            WHERE last_used IS NOT NULL
            ORDER BY last_used DESC
            LIMIT ?
        ''', (limit,))

        projects = [dict(row) for row in cursor.fetchall()]
        cursor.close()

        return projects

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a setting value"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        cursor.close()

        return result[0] if result else default

    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value)
                VALUES (?, ?)
            ''', (key, value))

            self.conn.commit()
            cursor.close()

    def delete_activities_by_timerange(
        self, start_time: datetime, end_time: datetime, app_name: str
    ) -> int:
        """Delete all activities in a time range for a specific app"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                DELETE FROM activities
                WHERE timestamp >= ?
                  AND timestamp < ?
                  AND app_name = ?
            ''', (start_time.strftime(_SQLITE_DT_FMT), end_time.strftime(_SQLITE_DT_FMT), app_name))

            rows_affected = cursor.rowcount
            self.conn.commit()
            cursor.close()

        return rows_affected

    def get_activities_in_timerange(
        self, start_time: datetime, end_time: datetime, app_name: str
    ) -> list[dict[str, Any]]:
        """Get activities matched by the timerange operations.

        Uses the same boundary semantics as assign/delete_by_timerange
        (start inclusive, end exclusive) so callers can capture undo data.
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM activities
            WHERE timestamp >= ?
              AND timestamp < ?
              AND app_name = ?
        ''', (start_time.strftime(_SQLITE_DT_FMT), end_time.strftime(_SQLITE_DT_FMT), app_name))

        activities = []
        for row in cursor.fetchall():
            activity = dict(row)
            if isinstance(activity['timestamp'], str):
                activity['timestamp'] = datetime.fromisoformat(activity['timestamp'])
            activities.append(activity)

        cursor.close()
        return activities

    def restore_activities(self, activities: list[dict[str, Any]]) -> int:
        """Re-insert previously deleted activities (undo support).

        Restores rows with their original IDs and project assignments.
        """
        if not activities:
            return 0

        with self._write_lock:
            cursor = self.conn.cursor()
            restored = 0

            for activity in activities:
                timestamp = activity['timestamp']
                if isinstance(timestamp, datetime):
                    timestamp = timestamp.strftime(_SQLITE_DT_FMT)

                cursor.execute('''
                    INSERT OR IGNORE INTO activities
                        (id, timestamp, app_name, window_title, duration,
                         category, project_id, is_idle, process_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    activity['id'],
                    timestamp,
                    activity['app_name'],
                    activity.get('window_title'),
                    activity['duration'],
                    activity.get('category'),
                    activity.get('project_id'),
                    activity.get('is_idle', False),
                    activity.get('process_path'),
                ))
                restored += cursor.rowcount

            self.conn.commit()
            cursor.close()

        return restored

    def get_total_duration(
        self,
        start_date: datetime,
        end_date: datetime,
        include_idle: bool = False,
    ) -> int:
        """Get the summed activity duration in seconds for a time range."""
        cursor = self.conn.cursor()

        query = '''
            SELECT COALESCE(SUM(duration), 0) FROM activities
            WHERE timestamp >= ? AND timestamp <= ?
        '''
        if not include_idle:
            query += ' AND is_idle = 0'

        cursor.execute(query, (
            start_date.strftime(_SQLITE_DT_FMT), end_date.strftime(_SQLITE_DT_FMT)
        ))
        total = cursor.fetchone()[0]
        cursor.close()

        return int(total)

    def create_project_rule(
        self,
        project_id: int,
        field: str,
        pattern: str,
        match_type: str = 'contains',
    ) -> int:
        """Create an assignment rule.

        Args:
            project_id: Target project
            field: 'app' or 'title'
            pattern: Substring or regex to match
            match_type: 'contains' or 'regex'
        """
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO project_rules (project_id, field, match_type, pattern)
                VALUES (?, ?, ?, ?)
            ''', (project_id, field, match_type, pattern))

            rule_id = cursor.lastrowid
            self.conn.commit()
            cursor.close()

        return int(rule_id) if rule_id else 0

    def get_project_rules(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        """Get all assignment rules ordered by priority."""
        cursor = self.conn.cursor()

        query = 'SELECT * FROM project_rules'
        if enabled_only:
            query += ' WHERE enabled = 1'
        query += ' ORDER BY priority, id'

        cursor.execute(query)
        rules = [dict(row) for row in cursor.fetchall()]
        cursor.close()

        return rules

    def update_project_rule(
        self,
        rule_id: int,
        project_id: int,
        field: str,
        pattern: str,
        match_type: str,
    ) -> None:
        """Update an existing assignment rule."""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE project_rules
                SET project_id = ?, field = ?, pattern = ?, match_type = ?
                WHERE id = ?
            ''', (project_id, field, pattern, match_type, rule_id))
            self.conn.commit()
            cursor.close()

    def delete_project_rule(self, rule_id: int) -> None:
        """Delete an assignment rule by ID."""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM project_rules WHERE id = ?', (rule_id,))
            self.conn.commit()
            cursor.close()

    def set_project_rule_enabled(self, rule_id: int, enabled: bool) -> None:
        """Enable or disable an assignment rule."""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute(
                'UPDATE project_rules SET enabled = ? WHERE id = ?',
                (enabled, rule_id),
            )
            self.conn.commit()
            cursor.close()

    def close(self) -> None:
        """Close database connection"""
        if self.conn:
            self.conn.close()
