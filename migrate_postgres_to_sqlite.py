"""
Migration script: PostgreSQL -> SQLite
Copies all data from PostgreSQL to SQLite database
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()


def migrate():
    """Migrate data from PostgreSQL to SQLite"""

    print("Starting migration from PostgreSQL to SQLite...")

    # Connect to PostgreSQL
    print("\nConnecting to PostgreSQL...")
    try:
        pg_conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'timetracker'),
            user=os.getenv('DB_USER', 'timetracker'),
            password=os.getenv('DB_PASSWORD', ''),
            port=os.getenv('DB_PORT', '5432')
        )
        print("OK - PostgreSQL connected")
    except Exception as e:
        print(f"ERROR - PostgreSQL connection failed: {e}")
        print("\nMake sure PostgreSQL is running and .env is configured correctly")
        return

    # Connect to SQLite
    print("\nConnecting to SQLite...")
    db_dir = Path.home() / '.timetracker'
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / 'timetracker.db'

    sqlite_conn = sqlite3.connect(str(db_path))
    sqlite_conn.row_factory = sqlite3.Row
    print(f"OK - SQLite connected ({db_path})")

    # Create tables in SQLite
    print("\nCreating SQLite tables...")
    cursor = sqlite_conn.cursor()

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

    # Create indexes
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_activities_timestamp
        ON activities(timestamp)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_activities_project
        ON activities(project_id)
    ''')

    sqlite_conn.commit()
    print("OK - Tables created")

    # Migrate Projects
    print("\nMigrating projects...")
    pg_cursor = pg_conn.cursor(cursor_factory=RealDictCursor)
    pg_cursor.execute('SELECT * FROM projects ORDER BY id')
    projects = pg_cursor.fetchall()

    project_id_map = {}  # Map old IDs to new IDs

    for project in projects:
        cursor.execute('''
            INSERT INTO projects (name, color, created_at)
            VALUES (?, ?, ?)
        ''', (project['name'], project['color'], project['created_at']))

        old_id = project['id']
        new_id = cursor.lastrowid
        project_id_map[old_id] = new_id

    sqlite_conn.commit()
    print(f"OK - Migrated {len(projects)} projects")

    # Migrate Activities
    print("\nMigrating activities...")
    pg_cursor.execute('SELECT * FROM activities ORDER BY timestamp')
    activities = pg_cursor.fetchall()

    for activity in activities:
        # Map old project_id to new project_id
        project_id = activity['project_id']
        if project_id:
            project_id = project_id_map.get(project_id)

        cursor.execute('''
            INSERT INTO activities (timestamp, app_name, window_title, duration,
                                   category, project_id, is_idle, process_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            activity['timestamp'],
            activity['app_name'],
            activity['window_title'],
            activity['duration'],
            activity.get('category'),
            project_id,
            activity.get('is_idle', False),
            activity.get('process_path')
        ))

    sqlite_conn.commit()
    print(f"OK - Migrated {len(activities)} activities")

    # Migrate Settings
    print("\nMigrating settings...")
    pg_cursor.execute('SELECT * FROM settings')
    settings = pg_cursor.fetchall()

    for setting in settings:
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        ''', (setting['key'], setting['value']))

    sqlite_conn.commit()
    print(f"OK - Migrated {len(settings)} settings")

    # Close connections
    pg_cursor.close()
    pg_conn.close()
    sqlite_conn.close()

    print("\n" + "="*50)
    print("Migration completed successfully!")
    print("="*50)
    print(f"\nSQLite database location: {db_path}")
    print(f"Projects: {len(projects)}")
    print(f"Activities: {len(activities)}")
    print(f"Settings: {len(settings)}")
    print("\nYou can now start the application with SQLite!")


if __name__ == '__main__':
    migrate()
