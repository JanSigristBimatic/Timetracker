"""Tests for the database extensions (rules, undo support, totals)"""
from datetime import datetime, timedelta

import pytest

from core.database import Database

BASE = datetime(2024, 1, 15, 9, 0, 0)


@pytest.fixture
def db(tmp_path):
    """Temporary real database"""
    database = Database(db_path=str(tmp_path / "test.db"))
    yield database
    database.close()


class TestProjectRules:
    def test_create_and_get_rules(self, db):
        project_id = db.create_project("Rail")
        rule_id = db.create_project_rule(project_id, "title", "bahnhof")

        rules = db.get_project_rules()
        assert len(rules) == 1
        rule = next(r for r in rules if r["id"] == rule_id)
        assert rule["project_id"] == project_id
        assert rule["field"] == "title"
        assert rule["match_type"] == "contains"
        assert rule["pattern"] == "bahnhof"
        assert rule["enabled"] == 1

    def test_enabled_only_filter(self, db):
        project_id = db.create_project("Rail")
        rule_id = db.create_project_rule(project_id, "title", "a")
        db.set_project_rule_enabled(rule_id, False)

        assert all(
            r["id"] != rule_id for r in db.get_project_rules(enabled_only=True)
        )

    def test_delete_rule(self, db):
        project_id = db.create_project("Rail")
        rule_id = db.create_project_rule(project_id, "app", "code.exe")

        db.delete_project_rule(rule_id)
        assert all(r["id"] != rule_id for r in db.get_project_rules())

    def test_update_rule(self, db):
        project_a = db.create_project("A")
        project_b = db.create_project("B")
        rule_id = db.create_project_rule(project_a, "title", "alt")

        db.update_project_rule(rule_id, project_b, "app", "neu.exe", "regex")

        rule = next(r for r in db.get_project_rules() if r["id"] == rule_id)
        assert rule["project_id"] == project_b
        assert rule["field"] == "app"
        assert rule["pattern"] == "neu.exe"
        assert rule["match_type"] == "regex"

    def test_rules_deleted_with_project(self, db):
        project_id = db.create_project("Temp")
        db.create_project_rule(project_id, "title", "x")

        db.delete_project(project_id)

        assert all(
            r["project_id"] != project_id for r in db.get_project_rules()
        )


class TestUndoSupport:
    def _save(self, db, start, minutes=30, app="Code.exe"):
        return db.save_activity(
            app_name=app,
            window_title="test",
            start_time=start,
            end_time=start + timedelta(minutes=minutes),
        )

    def test_get_activities_in_timerange_boundaries(self, db):
        self._save(db, BASE)
        self._save(db, BASE + timedelta(hours=1))

        # End exclusive: second activity at 10:00 not included
        result = db.get_activities_in_timerange(
            BASE, BASE + timedelta(hours=1), "Code.exe"
        )
        assert len(result) == 1
        assert result[0]["timestamp"] == BASE

    def test_restore_deleted_activities(self, db):
        project_id = db.create_project("Rail")
        activity_id = self._save(db, BASE)
        db.assign_activity_to_project(activity_id, project_id)

        rows = db.get_activities_in_timerange(
            BASE, BASE + timedelta(hours=1), "Code.exe"
        )
        deleted = db.delete_activities_by_timerange(
            BASE, BASE + timedelta(hours=1), "Code.exe"
        )
        assert deleted == 1
        assert db.get_activities() == []

        restored = db.restore_activities(rows)
        assert restored == 1

        activities = db.get_activities()
        assert len(activities) == 1
        assert activities[0]["id"] == activity_id
        assert activities[0]["project_id"] == project_id
        assert activities[0]["timestamp"] == BASE

    def test_restore_is_idempotent(self, db):
        self._save(db, BASE)
        rows = db.get_activities_in_timerange(
            BASE, BASE + timedelta(hours=1), "Code.exe"
        )

        # Restoring rows that still exist must not duplicate them
        assert db.restore_activities(rows) == 0
        assert len(db.get_activities()) == 1


class TestTotalsAndLastUsed:
    def test_get_total_duration_excludes_idle(self, db):
        db.save_activity("Code.exe", "t", BASE, BASE + timedelta(minutes=30))
        db.save_activity(
            "Idle", "", BASE + timedelta(hours=1),
            BASE + timedelta(hours=1, minutes=10), is_idle=True,
        )

        start = BASE.replace(hour=0)
        end = BASE.replace(hour=23)

        assert db.get_total_duration(start, end) == 30 * 60
        assert db.get_total_duration(start, end, include_idle=True) == 40 * 60

    def test_assign_activity_updates_last_used(self, db):
        project_id = db.create_project("Rail")
        activity_id = db.save_activity(
            "Code.exe", "t", BASE, BASE + timedelta(minutes=30)
        )

        db.assign_activity_to_project(activity_id, project_id)

        recent = db.get_recently_used_projects()
        assert any(p["id"] == project_id for p in recent)

    def test_assign_without_last_used_update(self, db):
        project_id = db.create_project("Rail")
        activity_id = db.save_activity(
            "Code.exe", "t", BASE, BASE + timedelta(minutes=30)
        )

        db.assign_activity_to_project(
            activity_id, project_id, update_last_used=False
        )

        recent = db.get_recently_used_projects()
        assert all(p["id"] != project_id for p in recent)


class TestPreventOverlapFlag:
    def test_overlap_prevention_disabled(self, db):
        db.save_activity("Code.exe", "work", BASE, BASE + timedelta(hours=2))

        # Calendar import overlapping tracked time must not shorten it
        db.save_activity(
            "Kalender", "Meeting",
            BASE + timedelta(minutes=30),
            BASE + timedelta(minutes=90),
            prevent_overlap=False,
        )

        activities = db.get_activities()
        code = next(a for a in activities if a["app_name"] == "Code.exe")
        assert code["duration"] == 2 * 3600  # untouched
        assert len(activities) == 2
