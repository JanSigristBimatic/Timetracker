"""
Cleanup-Script für Überlappungen in der TimeTracker-Datenbank

Dieses Script findet und behebt überlappende Aktivitäten:
- Erkennt Aktivitäten, die sich zeitlich überschneiden
- Behält die längere/wichtigere Aktivität
- Kürzt oder löscht überlappende Aktivitäten
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta


def parse_timestamp(ts):
    """Parse timestamp string to datetime"""
    if isinstance(ts, str):
        return datetime.fromisoformat(ts)
    return ts


def find_overlaps(conn):
    """Find all overlapping activities"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            a1.id as id1,
            a1.timestamp as start1,
            datetime(a1.timestamp, '+' || a1.duration || ' seconds') as end1,
            a1.duration as dur1,
            a1.app_name as app1,
            a1.is_idle as idle1,
            a2.id as id2,
            a2.timestamp as start2,
            datetime(a2.timestamp, '+' || a2.duration || ' seconds') as end2,
            a2.duration as dur2,
            a2.app_name as app2,
            a2.is_idle as idle2
        FROM activities a1
        JOIN activities a2 ON a1.id < a2.id
        WHERE a1.timestamp < a2.timestamp
          AND datetime(a1.timestamp, '+' || a1.duration || ' seconds') > a2.timestamp
        ORDER BY a1.timestamp
    """)

    overlaps = []
    for row in cursor.fetchall():
        overlaps.append({
            'id1': row[0],
            'start1': parse_timestamp(row[1]),
            'end1': parse_timestamp(row[2]),
            'dur1': row[3],
            'app1': row[4],
            'idle1': row[5],
            'id2': row[6],
            'start2': parse_timestamp(row[7]),
            'end2': parse_timestamp(row[8]),
            'dur2': row[9],
            'app2': row[10],
            'idle2': row[11],
        })

    cursor.close()
    return overlaps


def calculate_overlap_seconds(start1, end1, start2, end2):
    """Calculate overlap in seconds between two time ranges"""
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)

    if overlap_start >= overlap_end:
        return 0

    return (overlap_end - overlap_start).total_seconds()


def resolve_overlap(conn, overlap, dry_run=True):
    """
    Resolve an overlap by choosing which activity to keep/modify

    Strategy:
    1. If one is idle, remove the idle one
    2. If durations differ significantly, keep the longer one
    3. If same app, merge them
    4. Otherwise, shorten the first one to end when second starts
    """
    cursor = conn.cursor()

    id1 = overlap['id1']
    id2 = overlap['id2']
    start1 = overlap['start1']
    end1 = overlap['end1']
    dur1 = overlap['dur1']
    app1 = overlap['app1']
    idle1 = overlap['idle1']

    start2 = overlap['start2']
    end2 = overlap['end2']
    dur2 = overlap['dur2']
    app2 = overlap['app2']
    idle2 = overlap['idle2']

    overlap_seconds = calculate_overlap_seconds(start1, end1, start2, end2)

    action = None

    # Strategy 1: Remove idle activities
    if idle1 and not idle2:
        action = f"DELETE activity #{id1} (idle, overlaps {overlap_seconds}s with #{id2})"
        if not dry_run:
            cursor.execute("DELETE FROM activities WHERE id = ?", (id1,))
    elif idle2 and not idle1:
        action = f"DELETE activity #{id2} (idle, overlaps {overlap_seconds}s with #{id1})"
        if not dry_run:
            cursor.execute("DELETE FROM activities WHERE id = ?", (id2,))

    # Strategy 2: If activity 1 completely contains activity 2, delete activity 2
    elif start1 <= start2 and end1 >= end2:
        action = f"DELETE activity #{id2} (contained within #{id1})"
        if not dry_run:
            cursor.execute("DELETE FROM activities WHERE id = ?", (id2,))

    # Strategy 3: If activity 2 completely contains activity 1, delete activity 1
    elif start2 <= start1 and end2 >= end1:
        action = f"DELETE activity #{id1} (contained within #{id2})"
        if not dry_run:
            cursor.execute("DELETE FROM activities WHERE id = ?", (id1,))

    # Strategy 4: Same app - extend first, delete second
    elif app1 == app2:
        new_end = max(end1, end2)
        new_duration = int((new_end - start1).total_seconds())
        action = f"MERGE #{id1} and #{id2} (same app: {app1}, new duration: {new_duration}s)"
        if not dry_run:
            cursor.execute("UPDATE activities SET duration = ? WHERE id = ?", (new_duration, id1))
            cursor.execute("DELETE FROM activities WHERE id = ?", (id2,))

    # Strategy 5: Different apps - shorten first to end when second starts
    else:
        new_duration = int((start2 - start1).total_seconds())
        if new_duration > 0:
            action = f"SHORTEN #{id1} from {dur1}s to {new_duration}s (ends when #{id2} starts)"
            if not dry_run:
                cursor.execute("UPDATE activities SET duration = ? WHERE id = ?", (new_duration, id1))
        else:
            # First activity would have 0 duration - delete it
            action = f"DELETE activity #{id1} (would have 0 duration)"
            if not dry_run:
                cursor.execute("DELETE FROM activities WHERE id = ?", (id1,))

    cursor.close()
    return action


def main():
    print("TimeTracker Overlap Cleanup")
    print("=" * 80)

    # Connect to database
    db_path = Path.home() / '.timetracker' / 'timetracker.db'
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(str(db_path))

    # Find overlaps
    print("\nSuche nach Ueberlappungen...")
    overlaps = find_overlaps(conn)

    if not overlaps:
        print("Keine Ueberlappungen gefunden!")
        conn.close()
        return

    print(f"Gefunden: {len(overlaps)} Ueberlappungen")

    # Dry run first
    print("\n--- DRY RUN (keine Aenderungen) ---")
    for i, overlap in enumerate(overlaps, 1):
        action = resolve_overlap(conn, overlap, dry_run=True)
        print(f"{i}. {action}")

    # Ask for confirmation
    print("\n" + "=" * 80)
    response = input("Moechtest du diese Aenderungen durchfuehren? (ja/nein): ")

    if response.lower() not in ['ja', 'j', 'yes', 'y']:
        print("Abgebrochen.")
        conn.close()
        return

    # Actual cleanup
    print("\n--- CLEANUP ---")
    cleaned = 0

    # Re-fetch overlaps as they might have changed
    overlaps = find_overlaps(conn)

    while overlaps:
        overlap = overlaps[0]
        action = resolve_overlap(conn, overlap, dry_run=False)
        print(f"{cleaned + 1}. {action}")
        cleaned += 1
        conn.commit()

        # Re-fetch to get updated list
        overlaps = find_overlaps(conn)

    print(f"\nBereinigte Ueberlappungen: {cleaned}")

    # Show final stats
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM activities")
    total = cursor.fetchone()[0]
    print(f"Verbleibende Aktivitaeten: {total}")
    cursor.close()

    conn.close()
    print("\nFertig!")


if __name__ == "__main__":
    main()
