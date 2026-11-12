"""Tests for the dashboard aggregation helpers"""
from datetime import date, datetime, timedelta

from utils.project_stats import (
    aggregate_by_project,
    bucket_trend,
    compute_kpis,
    top_details_for_project,
)

BASE = datetime(2024, 1, 15, 9, 0, 0)  # a Monday


def make_activity(start, duration, app="Code.exe", title="main.py",
                  project_id=None, is_idle=False):
    return {
        "timestamp": start,
        "duration": duration,
        "app_name": app,
        "window_title": title,
        "project_id": project_id,
        "is_idle": is_idle,
    }


class TestAggregateByProject:
    def test_groups_and_ignores_idle(self):
        activities = [
            make_activity(BASE, 3600, project_id=1),
            make_activity(BASE + timedelta(hours=2), 1800, project_id=1),
            make_activity(BASE + timedelta(hours=4), 600),
            make_activity(BASE + timedelta(hours=5), 9999, is_idle=True),
        ]

        stats = aggregate_by_project(activities)

        assert stats[1]["seconds"] == 5400
        assert stats[1]["count"] == 2
        assert stats[1]["days"] == {BASE.date()}
        assert stats[None]["seconds"] == 600
        assert len(stats) == 2


class TestComputeKpis:
    def test_empty(self):
        kpis = compute_kpis([])
        assert kpis["active_seconds"] == 0
        assert kpis["assigned_ratio"] == 0.0
        assert kpis["busiest_day"] is None

    def test_ratios_and_busiest_day(self):
        day2 = BASE + timedelta(days=1)
        activities = [
            make_activity(BASE, 3600, project_id=1),      # assigned
            make_activity(BASE + timedelta(hours=2), 3600),  # unassigned
            make_activity(day2, 10800, project_id=1),
            make_activity(day2, 500, is_idle=True),       # ignored
        ]

        kpis = compute_kpis(activities)

        assert kpis["active_seconds"] == 18000
        assert kpis["assigned_ratio"] == (3600 + 10800) / 18000
        assert kpis["days_with_data"] == 2
        assert kpis["avg_seconds_per_day"] == 9000
        assert kpis["busiest_day"] == (day2.date(), 10800)


class TestBucketTrend:
    def test_weekly_buckets_include_empty_weeks(self):
        activities = [
            make_activity(BASE, 3600, project_id=1),
            # Two weeks later, week in between has no data
            make_activity(BASE + timedelta(days=14), 1800, project_id=2),
        ]

        labels, buckets, mode = bucket_trend(activities)

        assert mode == "week"
        assert len(buckets) == 3
        assert buckets[0] == {1: 3600}
        assert buckets[1] == {}
        assert buckets[2] == {2: 1800}
        assert labels[0] == "KW 3"

    def test_monthly_buckets_for_long_ranges(self):
        activities = [
            make_activity(BASE, 3600, project_id=1),
            make_activity(BASE + timedelta(days=200), 1800, project_id=1),
        ]

        labels, buckets, mode = bucket_trend(activities)

        assert mode == "month"
        assert len(buckets) == 8  # 15.01. + 200 days = 02.08. -> Jan..Aug
        assert labels[0] == "Jan 24"
        assert buckets[0] == {1: 3600}

    def test_empty(self):
        assert bucket_trend([]) == ([], [], "week")


class TestTopDetails:
    def test_top_apps_and_contents(self):
        activities = [
            make_activity(BASE, 3600, app="revit.exe",
                          title="Halle.rvt - Autodesk Revit", project_id=1),
            make_activity(BASE + timedelta(hours=1), 1800, app="revit.exe",
                          title="Halle.rvt - Autodesk Revit", project_id=1),
            make_activity(BASE + timedelta(hours=2), 900, app="chrome.exe",
                          title="Doku - Google Chrome", project_id=1),
            make_activity(BASE + timedelta(hours=3), 9999, app="word.exe",
                          title="x.docx - Word", project_id=2),  # other project
        ]

        top_apps, top_contents = top_details_for_project(activities, 1)

        assert top_apps[0] == ("revit.exe", 5400)
        assert top_apps[1] == ("chrome.exe", 900)
        assert len(top_apps) == 2
        assert top_contents[0] == ("Halle.rvt", 5400)

    def test_unassigned_project(self):
        activities = [make_activity(BASE, 600, app="notepad.exe", title="")]

        top_apps, top_contents = top_details_for_project(activities, None)

        assert top_apps == [("notepad.exe", 600)]
        assert top_contents == []
