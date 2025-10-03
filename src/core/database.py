import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()


class Database:
    def __init__(self):
        """Initialize database connection using environment variables or defaults"""
        self.conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'timetracker'),
            user=os.getenv('DB_USER', 'timetracker'),
            password=os.getenv('DB_PASSWORD', ''),
            port=os.getenv('DB_PORT', '5432')
        )
        self.conn.autocommit = False
        self.create_tables()

    def create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.conn.cursor()

        # Projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                color TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Activities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activities (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                app_name TEXT NOT NULL,
                window_title TEXT,
                duration INTEGER NOT NULL,
                category TEXT,
                project_id INTEGER,
                is_idle BOOLEAN DEFAULT FALSE,
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

    def save_activity(self, app_name, window_title, start_time, end_time, is_idle=False):
        """Save a tracked activity to the database"""
        duration = int((end_time - start_time).total_seconds())

        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO activities (timestamp, app_name, window_title, duration, is_idle)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        ''', (start_time, app_name, window_title, duration, is_idle))

        activity_id = cursor.fetchone()[0]
        self.conn.commit()
        cursor.close()

        return activity_id

    def get_activities(self, start_date=None, end_date=None, project_id=None):
        """Retrieve activities with optional filters"""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)

        query = 'SELECT * FROM activities WHERE 1=1'
        params = []

        if start_date:
            query += ' AND timestamp >= %s'
            params.append(start_date)

        if end_date:
            query += ' AND timestamp <= %s'
            params.append(end_date)

        if project_id:
            query += ' AND project_id = %s'
            params.append(project_id)

        query += ' ORDER BY timestamp DESC'

        cursor.execute(query, params)
        activities = cursor.fetchall()
        cursor.close()

        return activities

    def create_project(self, name, color='#3498db'):
        """Create a new project"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO projects (name, color)
            VALUES (%s, %s)
            RETURNING id
        ''', (name, color))

        project_id = cursor.fetchone()[0]
        self.conn.commit()
        cursor.close()

        return project_id

    def get_projects(self):
        """Get all projects"""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM projects ORDER BY name')
        projects = cursor.fetchall()
        cursor.close()

        return projects

    def assign_activity_to_project(self, activity_id, project_id):
        """Assign an activity to a project"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE activities
            SET project_id = %s
            WHERE id = %s
        ''', (project_id, activity_id))

        self.conn.commit()
        cursor.close()

    def get_setting(self, key, default=None):
        """Get a setting value"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = %s', (key,))
        result = cursor.fetchone()
        cursor.close()

        return result[0] if result else default

    def set_setting(self, key, value):
        """Set a setting value"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        ''', (key, value))

        self.conn.commit()
        cursor.close()

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
