"""Tests for the assignment rules engine"""
from datetime import datetime

from utils.assignment_rules import (
    FIELD_APP,
    FIELD_TITLE,
    MATCH_CONTAINS,
    MATCH_REGEX,
    AssignmentRulesEngine,
    apply_rules_to_activities,
    rule_matches,
)


class TestRuleMatches:
    def test_contains_case_insensitive(self):
        rule = {"id": 1, "match_type": MATCH_CONTAINS, "pattern": "bahnhof"}
        assert rule_matches(rule, "Projekt Bahnhof Nord.dwg")
        assert not rule_matches(rule, "Projekt Tunnel")

    def test_regex(self):
        rule = {"id": 1, "match_type": MATCH_REGEX, "pattern": r"\.dwg$"}
        assert rule_matches(rule, "plan.dwg")
        assert not rule_matches(rule, "plan.pdf")

    def test_invalid_regex_never_matches(self):
        rule = {"id": 1, "match_type": MATCH_REGEX, "pattern": "[invalid"}
        assert not rule_matches(rule, "anything")


class TestRulesEngine:
    def test_title_rule_matches(self, mock_db):
        project_id = mock_db.create_project("Bahnhof")
        mock_db.create_project_rule(project_id, FIELD_TITLE, "bahnhof")

        engine = AssignmentRulesEngine(mock_db)
        assert engine.match("revit.exe", "Bahnhof Nord - Revit") == project_id
        assert engine.match("revit.exe", "Tunnel Sued") is None

    def test_app_rule_matches(self, mock_db):
        project_id = mock_db.create_project("Development")
        mock_db.create_project_rule(project_id, FIELD_APP, "code.exe")

        engine = AssignmentRulesEngine(mock_db)
        assert engine.match("Code.exe", "irrelevant") == project_id

    def test_first_rule_wins(self, mock_db):
        first = mock_db.create_project("First")
        second = mock_db.create_project("Second")
        mock_db.create_project_rule(first, FIELD_TITLE, "report")
        mock_db.create_project_rule(second, FIELD_TITLE, "report")

        engine = AssignmentRulesEngine(mock_db)
        assert engine.match("word.exe", "Monthly Report") == first

    def test_disabled_rule_ignored(self, mock_db):
        project_id = mock_db.create_project("Disabled")
        rule_id = mock_db.create_project_rule(project_id, FIELD_TITLE, "test")
        mock_db.set_project_rule_enabled(rule_id, False)

        engine = AssignmentRulesEngine(mock_db)
        assert engine.match("app.exe", "test window") is None

    def test_reload_picks_up_new_rules(self, mock_db):
        engine = AssignmentRulesEngine(mock_db)
        assert engine.match("app.exe", "alpha") is None

        project_id = mock_db.create_project("Alpha")
        mock_db.create_project_rule(project_id, FIELD_TITLE, "alpha")

        # Cached: still None until reload
        assert engine.match("app.exe", "alpha") is None
        engine.reload()
        assert engine.match("app.exe", "alpha") == project_id


class TestApplyRulesToActivities:
    def test_assigns_only_unassigned(self, mock_db):
        project_id = mock_db.create_project("Rail")
        other_id = mock_db.create_project("Other")
        mock_db.create_project_rule(project_id, FIELD_TITLE, "rail")

        base = datetime(2024, 1, 15, 9, 0, 0)
        a1 = mock_db.save_activity(
            "revit.exe", "Rail project", base,
            base.replace(minute=30),
        )
        a2 = mock_db.save_activity(
            "revit.exe", "Rail project 2", base.replace(hour=10),
            base.replace(hour=10, minute=30),
        )
        mock_db.assign_activity_to_project(a2, other_id)

        activities = mock_db.get_activities()
        assigned = apply_rules_to_activities(mock_db, activities)

        assert assigned == 1
        activities = {a["id"]: a for a in mock_db.get_activities()}
        assert activities[a1]["project_id"] == project_id
        assert activities[a2]["project_id"] == other_id  # untouched
