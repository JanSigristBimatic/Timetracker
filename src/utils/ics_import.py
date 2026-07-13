"""Minimal ICS (iCalendar) parser for importing calendar events.

Supports single VEVENT entries with DTSTART/DTEND in UTC ('Z' suffix),
floating local time, or TZID-annotated local time (interpreted as local).
All-day events (VALUE=DATE), cancelled events, and recurring events
(RRULE) are skipped - this keeps the parser dependency-free and safe.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


def parse_ics_events(ics_text: str) -> list[dict[str, Any]]:
    """Parse VEVENT entries from ICS file content.

    Args:
        ics_text: Raw content of an .ics file

    Returns:
        List of dicts with 'start' (datetime), 'end' (datetime),
        'summary' (str), sorted by start time. Events that cannot be
        parsed reliably are skipped.
    """
    events = []

    for block in _extract_event_blocks(_unfold_lines(ics_text)):
        event = _parse_event_block(block)
        if event:
            events.append(event)

    events.sort(key=lambda e: e['start'])
    return events


def _unfold_lines(ics_text: str) -> list[str]:
    """Unfold ICS lines (continuation lines start with space or tab)."""
    unfolded: list[str] = []

    for raw_line in ics_text.splitlines():
        if raw_line[:1] in (' ', '\t') and unfolded:
            unfolded[-1] += raw_line[1:]
        else:
            unfolded.append(raw_line)

    return unfolded


def _extract_event_blocks(lines: list[str]) -> list[list[str]]:
    """Group lines into VEVENT blocks."""
    blocks: list[list[str]] = []
    current: Optional[list[str]] = None

    for line in lines:
        stripped = line.strip()
        if stripped == 'BEGIN:VEVENT':
            current = []
        elif stripped == 'END:VEVENT':
            if current is not None:
                blocks.append(current)
            current = None
        elif current is not None:
            current.append(line)

    return blocks


def _parse_event_block(lines: list[str]) -> Optional[dict[str, Any]]:
    """Parse one VEVENT block into an event dict, or None if unsupported."""
    start = None
    end = None
    summary = ''
    cancelled = False
    recurring = False

    for line in lines:
        name, params, value = _split_content_line(line)
        if name == 'DTSTART':
            start = _parse_ics_datetime(value, params)
        elif name == 'DTEND':
            end = _parse_ics_datetime(value, params)
        elif name == 'SUMMARY':
            summary = _unescape_text(value)
        elif name == 'STATUS' and value.strip().upper() == 'CANCELLED':
            cancelled = True
        elif name == 'RRULE':
            recurring = True

    if cancelled or recurring:
        return None

    if start is None or end is None or end <= start:
        return None

    return {'start': start, 'end': end, 'summary': summary or '(Ohne Titel)'}


def _split_content_line(line: str) -> tuple[str, str, str]:
    """Split an ICS content line into (name, params, value)."""
    if ':' not in line:
        return '', '', ''

    prop, value = line.split(':', 1)

    if ';' in prop:
        name, params = prop.split(';', 1)
    else:
        name, params = prop, ''

    return name.strip().upper(), params.upper(), value


def _parse_ics_datetime(value: str, params: str) -> Optional[datetime]:
    """Parse an ICS date-time value into a naive local datetime.

    All-day dates (VALUE=DATE) return None because they carry no
    meaningful time span for time tracking.
    """
    value = value.strip()

    if 'VALUE=DATE' in params and 'T' not in value:
        return None

    match = re.match(r'^(\d{8})T(\d{6})(Z?)$', value)
    if not match:
        return None

    date_part, time_part, utc_flag = match.groups()

    try:
        dt = datetime.strptime(f"{date_part}{time_part}", '%Y%m%d%H%M%S')
    except ValueError:
        return None

    if utc_flag == 'Z':
        # Convert UTC to local time, then drop tzinfo (DB stores naive local)
        dt = dt.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)

    # TZID values are interpreted as local time - good enough for
    # single-timezone usage, documented limitation
    return dt


def _unescape_text(value: str) -> str:
    """Unescape ICS text values (\\n, \\, \\; \\,)."""
    return (
        value.replace('\\n', ' ')
        .replace('\\N', ' ')
        .replace('\\,', ',')
        .replace('\\;', ';')
        .replace('\\\\', '\\')
        .strip()
    )
