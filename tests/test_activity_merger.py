"""Tests for the activity merge logic"""
from datetime import datetime, timedelta

from utils.activity_merger import merge_activities


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


BASE = datetime(2024, 1, 15, 9, 0, 0)


class TestMergeActivities:
    def test_empty_input(self):
        assert merge_activities([]) == []

    def test_short_activities_filtered(self):
        activities = [make_activity(BASE, 5)]
        assert merge_activities(activities, min_duration=10) == []

    def test_single_activity(self):
        activities = [make_activity(BASE, 120)]
        merged = merge_activities(activities)

        assert len(merged) == 1
        assert merged[0]["duration"] == 120
        assert merged[0]["tracked_duration"] == 120
        assert merged[0]["end_time"] == BASE + timedelta(seconds=120)

    def test_same_app_within_gap_merges(self):
        activities = [
            make_activity(BASE, 60),
            make_activity(BASE + timedelta(seconds=90), 60),  # 30s gap
        ]
        merged = merge_activities(activities, merge_gap=60)

        assert len(merged) == 1
        assert merged[0]["duration"] == 150  # includes the gap
        assert merged[0]["tracked_duration"] == 120  # excludes the gap

    def test_same_app_beyond_gap_stays_separate(self):
        activities = [
            make_activity(BASE, 60),
            make_activity(BASE + timedelta(seconds=200), 60),  # 140s gap
        ]
        merged = merge_activities(activities, merge_gap=60)

        assert len(merged) == 2

    def test_different_apps_never_merge(self):
        activities = [
            make_activity(BASE, 60, app="Code.exe"),
            make_activity(BASE + timedelta(seconds=70), 60, app="chrome.exe"),
        ]
        merged = merge_activities(activities, merge_gap=60)

        assert len(merged) == 2

    def test_same_project_uses_larger_gap(self):
        activities = [
            make_activity(BASE, 60, project_id=1),
            make_activity(BASE + timedelta(seconds=180), 60, project_id=1),  # 120s gap
        ]
        merged = merge_activities(activities, merge_gap=60, project_merge_gap=180)

        assert len(merged) == 1

    def test_idle_never_merges(self):
        activities = [
            make_activity(BASE, 60, is_idle=True),
            make_activity(BASE + timedelta(seconds=70), 60, is_idle=True),
        ]
        merged = merge_activities(activities, merge_gap=60)

        assert len(merged) == 2

    def test_latest_window_title_kept(self):
        activities = [
            make_activity(BASE, 60, title="first.py"),
            make_activity(BASE + timedelta(seconds=70), 60, title="second.py"),
        ]
        merged = merge_activities(activities, merge_gap=60)

        assert merged[0]["window_title"] == "second.py"

    def test_unsorted_input_is_sorted(self):
        activities = [
            make_activity(BASE + timedelta(seconds=70), 60),
            make_activity(BASE, 60),
        ]
        merged = merge_activities(activities, merge_gap=60)

        assert len(merged) == 1
        assert merged[0]["timestamp"] == BASE

    def test_contained_activity_does_not_shrink_block(self):
        activities = [
            make_activity(BASE, 300),
            make_activity(BASE + timedelta(seconds=60), 30),  # inside the first
        ]
        merged = merge_activities(activities, merge_gap=60)

        assert len(merged) == 1
        assert merged[0]["end_time"] == BASE + timedelta(seconds=300)
