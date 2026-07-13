"""Tests for the ICS calendar parser"""
from datetime import datetime, timedelta, timezone

from utils.ics_import import parse_ics_events

SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20240115T090000
DTEND:20240115T100000
SUMMARY:Team Meeting
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=Europe/Zurich:20240115T140000
DTEND;TZID=Europe/Zurich:20240115T153000
SUMMARY:Baustellenbesprechung\\, Bahnhof
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20240116
DTEND;VALUE=DATE:20240117
SUMMARY:Ganztagestermin
END:VEVENT
BEGIN:VEVENT
DTSTART:20240117T090000
DTEND:20240117T100000
RRULE:FREQ=WEEKLY
SUMMARY:Serientermin
END:VEVENT
BEGIN:VEVENT
DTSTART:20240118T090000
DTEND:20240118T100000
STATUS:CANCELLED
SUMMARY:Abgesagt
END:VEVENT
END:VCALENDAR
"""


class TestParseIcsEvents:
    def test_floating_local_time(self):
        events = parse_ics_events(SAMPLE_ICS)
        meeting = next(e for e in events if e["summary"] == "Team Meeting")

        assert meeting["start"] == datetime(2024, 1, 15, 9, 0)
        assert meeting["end"] == datetime(2024, 1, 15, 10, 0)

    def test_tzid_treated_as_local(self):
        events = parse_ics_events(SAMPLE_ICS)
        meeting = next(e for e in events if "Baustellen" in e["summary"])

        assert meeting["start"] == datetime(2024, 1, 15, 14, 0)
        assert meeting["summary"] == "Baustellenbesprechung, Bahnhof"

    def test_allday_recurring_and_cancelled_skipped(self):
        events = parse_ics_events(SAMPLE_ICS)
        summaries = {e["summary"] for e in events}

        assert "Ganztagestermin" not in summaries
        assert "Serientermin" not in summaries
        assert "Abgesagt" not in summaries
        assert len(events) == 2

    def test_utc_converted_to_local(self):
        ics = (
            "BEGIN:VEVENT\n"
            "DTSTART:20240115T080000Z\n"
            "DTEND:20240115T090000Z\n"
            "SUMMARY:UTC Event\n"
            "END:VEVENT\n"
        )
        events = parse_ics_events(ics)

        assert len(events) == 1
        expected_start = (
            datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc)
            .astimezone()
            .replace(tzinfo=None)
        )
        assert events[0]["start"] == expected_start
        assert events[0]["end"] - events[0]["start"] == timedelta(hours=1)

    def test_folded_summary_line(self):
        ics = (
            "BEGIN:VEVENT\n"
            "DTSTART:20240115T080000\n"
            "DTEND:20240115T090000\n"
            "SUMMARY:Langer Titel der\n"
            " weitergeht\n"
            "END:VEVENT\n"
        )
        events = parse_ics_events(ics)

        assert events[0]["summary"] == "Langer Titel derweitergeht"

    def test_invalid_event_skipped(self):
        ics = (
            "BEGIN:VEVENT\n"
            "DTSTART:20240115T100000\n"
            "DTEND:20240115T090000\n"
            "SUMMARY:Ende vor Start\n"
            "END:VEVENT\n"
        )
        assert parse_ics_events(ics) == []

    def test_events_sorted_by_start(self):
        events = parse_ics_events(SAMPLE_ICS)
        starts = [e["start"] for e in events]
        assert starts == sorted(starts)
