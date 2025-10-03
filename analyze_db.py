import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import sys
import io

# Set UTF-8 encoding for output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Connect to database
db_path = Path.home() / '.timetracker' / 'timetracker.db'
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

cursor = conn.cursor()

# Get today's date
today = datetime.now().date()
print(f"Analyse fuer: {today}")
print("=" * 80)

# Total activities today
cursor.execute("""
    SELECT
        COUNT(*) as count,
        SUM(duration) as total_seconds,
        SUM(CASE WHEN is_idle = 1 THEN duration ELSE 0 END) as idle_seconds,
        SUM(CASE WHEN is_idle = 0 THEN duration ELSE 0 END) as active_seconds
    FROM activities
    WHERE date(timestamp) = date('now')
""")
row = cursor.fetchone()
print(f"\nGESAMTSTATISTIK:")
print(f"   Aktivitaeten: {row['count']}")
print(f"   Gesamt: {row['total_seconds']/3600:.2f}h ({row['total_seconds']}s)")
print(f"   Aktiv: {row['active_seconds']/3600:.2f}h ({row['active_seconds']}s)")
print(f"   Idle: {row['idle_seconds']/3600:.2f}h ({row['idle_seconds']}s)")

# Check for overlapping activities
cursor.execute("""
    SELECT
        a1.id as id1,
        a1.timestamp as start1,
        datetime(a1.timestamp, '+' || a1.duration || ' seconds') as end1,
        a1.duration as dur1,
        a1.app_name as app1,
        a2.id as id2,
        a2.timestamp as start2,
        datetime(a2.timestamp, '+' || a2.duration || ' seconds') as end2,
        a2.duration as dur2,
        a2.app_name as app2
    FROM activities a1
    JOIN activities a2 ON a1.id < a2.id
    WHERE date(a1.timestamp) = date('now')
      AND date(a2.timestamp) = date('now')
      AND a1.timestamp < a2.timestamp
      AND datetime(a1.timestamp, '+' || a1.duration || ' seconds') > a2.timestamp
    LIMIT 10
""")
overlaps = cursor.fetchall()
if overlaps:
    print(f"\nUEBERLAPPUNGEN GEFUNDEN: {len(overlaps)}")
    for overlap in overlaps[:5]:
        print(f"   #{overlap['id1']} ({overlap['app1']}) {overlap['start1']} - {overlap['end1']} ({overlap['dur1']}s)")
        print(f"   #{overlap['id2']} ({overlap['app2']}) {overlap['start2']} - {overlap['end2']} ({overlap['dur2']}s)")
        print()

# Top apps by time
cursor.execute("""
    SELECT
        app_name,
        COUNT(*) as count,
        SUM(duration) as total_seconds,
        SUM(CASE WHEN is_idle = 1 THEN duration ELSE 0 END) as idle_seconds
    FROM activities
    WHERE date(timestamp) = date('now')
      AND is_idle = 0
    GROUP BY app_name
    ORDER BY total_seconds DESC
    LIMIT 10
""")
print(f"\nTOP 10 APPS (Aktive Zeit):")
for row in cursor.fetchall():
    print(f"   {row['app_name']:<30} {row['total_seconds']/3600:>6.2f}h  ({row['count']:>4} Aktivitaeten)")

# Very long activities (potential issues)
cursor.execute("""
    SELECT
        id,
        timestamp,
        app_name,
        window_title,
        duration,
        is_idle
    FROM activities
    WHERE date(timestamp) = date('now')
      AND duration > 3600
    ORDER BY duration DESC
    LIMIT 10
""")
long_activities = cursor.fetchall()
if long_activities:
    print(f"\nSEHR LANGE AKTIVITAETEN (>1h):")
    for row in long_activities:
        idle_marker = " [IDLE]" if row['is_idle'] else ""
        print(f"   #{row['id']}: {row['app_name']:<25} {row['duration']/3600:.2f}h{idle_marker}")
        print(f"        {row['timestamp']} - {row['window_title'][:60] if row['window_title'] else 'N/A'}")

# Activities per hour distribution
cursor.execute("""
    SELECT
        strftime('%H', timestamp) as hour,
        COUNT(*) as count,
        SUM(duration) as total_seconds
    FROM activities
    WHERE date(timestamp) = date('now')
    GROUP BY hour
    ORDER BY hour
""")
print(f"\nVERTEILUNG PRO STUNDE:")
for row in cursor.fetchall():
    bar = '#' * int(row['total_seconds'] / 360)  # 1 block = 6 minutes
    print(f"   {row['hour']}:00  {row['total_seconds']/3600:>5.2f}h  {bar}")

# Check for duplicate activities
cursor.execute("""
    SELECT
        timestamp,
        app_name,
        window_title,
        duration,
        COUNT(*) as count
    FROM activities
    WHERE date(timestamp) = date('now')
    GROUP BY timestamp, app_name, window_title, duration
    HAVING count > 1
    LIMIT 5
""")
duplicates = cursor.fetchall()
if duplicates:
    print(f"\nDUPLIKATE GEFUNDEN:")
    for row in duplicates:
        print(f"   {row['count']}x: {row['app_name']} @ {row['timestamp']} ({row['duration']}s)")

cursor.close()
conn.close()
