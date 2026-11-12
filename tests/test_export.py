"""Tests for export row builders and file output"""
from datetime import datetime, timedelta

import openpyxl

from utils.export import (
    Exporter,
    UNASSIGNED_LABEL,
    day_project_rows,
    project_summary_rows,
)

BASE = datetime(2026, 11, 2, 8, 0, 0)


def _activity(offset_hours, seconds, project_id=None, is_idle=False, app="Code.exe"):
    return {
        "timestamp": BASE + timedelta(hours=offset_hours),
        "duration": seconds,
        "app_name": app,
        "window_title": "Fenster ä",
        "project_id": project_id,
        "is_idle": is_idle,
    }


def test_project_summary_ignores_idle_and_labels_unassigned():
    activities = [
        _activity(0, 3600, project_id=1),
        _activity(1, 1800),
        _activity(2, 7200, is_idle=True),
    ]

    rows = project_summary_rows(activities, {1: "Bahnhof"})

    by_name = {r["Projekt"]: r for r in rows}
    assert by_name["Bahnhof"]["Gesamtzeit (Stunden)"] == 1.0
    assert by_name[UNASSIGNED_LABEL]["Gesamtzeit (Minuten)"] == 30.0
    assert len(rows) == 2


def test_day_project_rows_group_by_day_and_project():
    activities = [
        _activity(0, 1800, project_id=1),
        _activity(1, 1800, project_id=1),
        _activity(24, 3600, project_id=1),
    ]

    rows = day_project_rows(activities, {1: "Bahnhof"})

    assert rows == [
        {"Datum": "2026-11-02", "Projekt": "Bahnhof", "Stunden": 1.0},
        {"Datum": "2026-11-03", "Projekt": "Bahnhof", "Stunden": 1.0},
    ]


def test_csv_has_bom_for_excel(mock_db, tmp_path):
    mock_db.save_activity("Code.exe", "Fenster ä", BASE, BASE + timedelta(minutes=5))
    path = tmp_path / "out.csv"

    Exporter(mock_db).export_csv(BASE - timedelta(days=1), BASE + timedelta(days=1), str(path))

    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert "Fenster ä" in raw.decode("utf-8-sig")


def test_excel_contains_day_project_sheet(mock_db, tmp_path):
    project_id = mock_db.create_project("Bahnhof")
    activity_id = mock_db.save_activity("Code.exe", "x", BASE, BASE + timedelta(hours=2))
    mock_db.assign_activity_to_project(activity_id, project_id)
    path = tmp_path / "out.xlsx"

    Exporter(mock_db).export_excel(BASE - timedelta(days=1), BASE + timedelta(days=1), str(path))

    workbook = openpyxl.load_workbook(path)
    assert "Tag x Projekt" in workbook.sheetnames
    sheet = workbook["Tag x Projekt"]
    assert [c.value for c in sheet[2]] == ["2026-11-02", "Bahnhof", 2]
