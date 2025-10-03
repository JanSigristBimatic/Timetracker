"""
Tests für Überlappungs-Prävention in der Database

Diese Tests stellen sicher, dass:
1. Keine überlappenden Aktivitäten gespeichert werden
2. Bestehende Aktivitäten korrekt gekürzt werden
3. Sehr kurze Aktivitäten korrekt behandelt werden
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from core.database import Database


@pytest.fixture
def temp_db():
    """Temporäre Datenbank für Tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock Path.home to use temp directory
        original_home = Path.home
        Path.home = lambda: Path(tmpdir)

        db = Database()
        yield db

        db.close()
        Path.home = original_home


def test_no_overlap_sequential_activities(temp_db):
    """Test: Sequentielle Aktivitäten ohne Überlappung"""
    # Activity 1: 10:00:00 - 10:01:00
    start1 = datetime(2025, 10, 3, 10, 0, 0)
    end1 = datetime(2025, 10, 3, 10, 1, 0)

    # Activity 2: 10:01:00 - 10:02:00 (direkt danach)
    start2 = datetime(2025, 10, 3, 10, 1, 0)
    end2 = datetime(2025, 10, 3, 10, 2, 0)

    id1 = temp_db.save_activity("App1", "Window1", start1, end1)
    id2 = temp_db.save_activity("App2", "Window2", start2, end2)

    assert id1 > 0
    assert id2 > 0

    activities = temp_db.get_activities()
    assert len(activities) == 2
    assert activities[0]['duration'] == 60
    assert activities[1]['duration'] == 60


def test_overlap_shortens_previous_activity(temp_db):
    """Test: Überlappung kürzt vorherige Aktivität"""
    # Activity 1: 10:00:00 - 10:02:00 (2 Minuten)
    start1 = datetime(2025, 10, 3, 10, 0, 0)
    end1 = datetime(2025, 10, 3, 10, 2, 0)

    # Activity 2: 10:01:00 - 10:03:00 (überlappt 1 Minute)
    start2 = datetime(2025, 10, 3, 10, 1, 0)
    end2 = datetime(2025, 10, 3, 10, 3, 0)

    id1 = temp_db.save_activity("App1", "Window1", start1, end1)
    id2 = temp_db.save_activity("App2", "Window2", start2, end2)

    assert id1 > 0
    assert id2 > 0

    activities = temp_db.get_activities()
    assert len(activities) == 2

    # Activity 1 sollte auf 1 Minute gekürzt sein (10:00 - 10:01)
    act1 = [a for a in activities if a['id'] == id1][0]
    assert act1['duration'] == 60  # 1 Minute statt 2

    # Activity 2 sollte unverändert sein
    act2 = [a for a in activities if a['id'] == id2][0]
    assert act2['duration'] == 120  # 2 Minuten


def test_complete_overlap_deletes_previous(temp_db):
    """Test: Vollständige Überlappung löscht vorherige Aktivität"""
    # Activity 1: 10:01:00 - 10:02:00
    start1 = datetime(2025, 10, 3, 10, 1, 0)
    end1 = datetime(2025, 10, 3, 10, 2, 0)

    # Activity 2: 10:00:00 - 10:03:00 (überdeckt Activity 1 komplett)
    start2 = datetime(2025, 10, 3, 10, 0, 0)
    end2 = datetime(2025, 10, 3, 10, 3, 0)

    id1 = temp_db.save_activity("App1", "Window1", start1, end1)
    id2 = temp_db.save_activity("App2", "Window2", start2, end2)

    assert id1 > 0
    assert id2 > 0

    activities = temp_db.get_activities()

    # Activity 1 sollte gelöscht sein (würde 0 Sekunden haben)
    act1_exists = any(a['id'] == id1 for a in activities)
    assert not act1_exists

    # Nur Activity 2 sollte existieren
    assert len(activities) == 1
    assert activities[0]['id'] == id2
    assert activities[0]['duration'] == 180


def test_multiple_overlaps(temp_db):
    """Test: Mehrere überlappende Aktivitäten"""
    # Activity 1: 10:00:00 - 10:05:00
    start1 = datetime(2025, 10, 3, 10, 0, 0)
    end1 = datetime(2025, 10, 3, 10, 5, 0)

    # Activity 2: 10:02:00 - 10:07:00
    start2 = datetime(2025, 10, 3, 10, 2, 0)
    end2 = datetime(2025, 10, 3, 10, 7, 0)

    # Activity 3: 10:03:00 - 10:08:00 (überlappt sowohl 1 als auch 2)
    start3 = datetime(2025, 10, 3, 10, 3, 0)
    end3 = datetime(2025, 10, 3, 10, 8, 0)

    id1 = temp_db.save_activity("App1", "Window1", start1, end1)
    id2 = temp_db.save_activity("App2", "Window2", start2, end2)
    id3 = temp_db.save_activity("App3", "Window3", start3, end3)

    activities = temp_db.get_activities()

    # Activity 1: 10:00 - 10:02 (2 Minuten)
    act1 = [a for a in activities if a['id'] == id1][0]
    assert act1['duration'] == 120

    # Activity 2: 10:02 - 10:03 (1 Minute)
    act2 = [a for a in activities if a['id'] == id2][0]
    assert act2['duration'] == 60

    # Activity 3: 10:03 - 10:08 (5 Minuten, unverändert)
    act3 = [a for a in activities if a['id'] == id3][0]
    assert act3['duration'] == 300


def test_no_overlap_gap_between_activities(temp_db):
    """Test: Aktivitäten mit Lücke dazwischen"""
    # Activity 1: 10:00:00 - 10:01:00
    start1 = datetime(2025, 10, 3, 10, 0, 0)
    end1 = datetime(2025, 10, 3, 10, 1, 0)

    # Activity 2: 10:02:00 - 10:03:00 (1 Minute Lücke)
    start2 = datetime(2025, 10, 3, 10, 2, 0)
    end2 = datetime(2025, 10, 3, 10, 3, 0)

    id1 = temp_db.save_activity("App1", "Window1", start1, end1)
    id2 = temp_db.save_activity("App2", "Window2", start2, end2)

    activities = temp_db.get_activities()
    assert len(activities) == 2

    # Beide Aktivitäten sollten unverändert sein
    assert activities[0]['duration'] == 60
    assert activities[1]['duration'] == 60


def test_one_second_overlap(temp_db):
    """Test: Minimale Überlappung von 1 Sekunde"""
    # Activity 1: 10:00:00 - 10:01:00
    start1 = datetime(2025, 10, 3, 10, 0, 0)
    end1 = datetime(2025, 10, 3, 10, 1, 0)

    # Activity 2: 10:00:59 - 10:02:00 (1 Sekunde Überlappung)
    start2 = datetime(2025, 10, 3, 10, 0, 59)
    end2 = datetime(2025, 10, 3, 10, 2, 0)

    id1 = temp_db.save_activity("App1", "Window1", start1, end1)
    id2 = temp_db.save_activity("App2", "Window2", start2, end2)

    activities = temp_db.get_activities()
    assert len(activities) == 2

    # Activity 1 sollte auf 59 Sekunden gekürzt sein
    act1 = [a for a in activities if a['id'] == id1][0]
    assert act1['duration'] == 59

    # Activity 2 sollte unverändert sein
    act2 = [a for a in activities if a['id'] == id2][0]
    assert act2['duration'] == 61


def test_idle_activity_overlap(temp_db):
    """Test: Idle-Aktivitäten werden auch gekürzt"""
    # Activity 1: 10:00:00 - 10:02:00 (idle)
    start1 = datetime(2025, 10, 3, 10, 0, 0)
    end1 = datetime(2025, 10, 3, 10, 2, 0)

    # Activity 2: 10:01:00 - 10:03:00 (active)
    start2 = datetime(2025, 10, 3, 10, 1, 0)
    end2 = datetime(2025, 10, 3, 10, 3, 0)

    id1 = temp_db.save_activity("Idle", "", start1, end1, is_idle=True)
    id2 = temp_db.save_activity("App2", "Window2", start2, end2, is_idle=False)

    activities = temp_db.get_activities()

    # Idle Activity sollte auf 1 Minute gekürzt sein
    act1 = [a for a in activities if a['id'] == id1][0]
    assert act1['duration'] == 60
    assert act1['is_idle'] == 1

    # Active Activity sollte unverändert sein
    act2 = [a for a in activities if a['id'] == id2][0]
    assert act2['duration'] == 120
    assert act2['is_idle'] == 0
