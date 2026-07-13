"""
Demo MCP Server - Simuliert externe Dienste
Beispiel: Slack-ähnlicher Server der Kommunikationszeiten tracked
"""
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta
import random

# Erstelle MCP Server
mcp = FastMCP("CommunicationTracker")


@mcp.tool()
def get_slack_activities(date: str = None) -> list[dict]:
    """
    Get Slack communication activities for a specific date

    Args:
        date: Date in format YYYY-MM-DD (default: today)

    Returns:
        List of Slack activities with timestamps and channels
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Simuliere Slack-Aktivitäten
    channels = ["#general", "#dev-team", "#project-x", "#random"]
    activities = []

    base_date = datetime.strptime(date, "%Y-%m-%d")

    # Generiere 5-10 zufällige Aktivitäten
    num_activities = random.randint(5, 10)
    for i in range(num_activities):
        hour = random.randint(8, 17)
        minute = random.randint(0, 59)
        duration = random.randint(5, 45)  # 5-45 Minuten

        start_time = base_date.replace(hour=hour, minute=minute)
        end_time = start_time + timedelta(minutes=duration)

        activities.append({
            "channel": random.choice(channels),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_minutes": duration,
            "message_count": random.randint(1, 20)
        })

    # Sortiere nach Zeit
    activities.sort(key=lambda x: x["start_time"])

    return activities


@mcp.tool()
def get_github_activities(date: str = None) -> list[dict]:
    """
    Get GitHub activity (commits, PRs, reviews) for a specific date

    Args:
        date: Date in format YYYY-MM-DD (default: today)

    Returns:
        List of GitHub activities
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    repos = ["timetracker", "web-app", "api-service"]
    activity_types = ["commit", "pull_request", "code_review"]

    activities = []
    base_date = datetime.strptime(date, "%Y-%m-%d")

    num_activities = random.randint(3, 8)
    for i in range(num_activities):
        hour = random.randint(9, 18)
        minute = random.randint(0, 59)
        duration = random.randint(10, 90)

        start_time = base_date.replace(hour=hour, minute=minute)
        end_time = start_time + timedelta(minutes=duration)

        activities.append({
            "repo": random.choice(repos),
            "type": random.choice(activity_types),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_minutes": duration
        })

    activities.sort(key=lambda x: x["start_time"])

    return activities


@mcp.tool()
def get_calendar_events(date: str = None) -> list[dict]:
    """
    Get calendar events (meetings) for a specific date

    Args:
        date: Date in format YYYY-MM-DD (default: today)

    Returns:
        List of calendar events
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    meetings = [
        "Daily Standup",
        "Sprint Planning",
        "1:1 with Manager",
        "Client Call",
        "Team Sync"
    ]

    events = []
    base_date = datetime.strptime(date, "%Y-%m-%d")

    num_events = random.randint(2, 5)
    for i in range(num_events):
        hour = random.randint(9, 16)
        duration = random.choice([30, 60, 90])

        start_time = base_date.replace(hour=hour, minute=0)
        end_time = start_time + timedelta(minutes=duration)

        events.append({
            "title": random.choice(meetings),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_minutes": duration,
            "attendees": random.randint(2, 8)
        })

    events.sort(key=lambda x: x["start_time"])

    return events


@mcp.resource("summary://{date}")
def get_daily_summary(date: str) -> str:
    """
    Get a summary of all activities for a date

    Args:
        date: Date in format YYYY-MM-DD

    Returns:
        Formatted summary string
    """
    slack = get_slack_activities(date)
    github = get_github_activities(date)
    calendar = get_calendar_events(date)

    total_slack_minutes = sum(a["duration_minutes"] for a in slack)
    total_github_minutes = sum(a["duration_minutes"] for a in github)
    total_meeting_minutes = sum(e["duration_minutes"] for e in calendar)

    summary = f"""
Activity Summary for {date}
{'=' * 40}

Communication (Slack):
  - {len(slack)} sessions
  - {total_slack_minutes} minutes total
  - Channels: {', '.join(set(a['channel'] for a in slack))}

Development (GitHub):
  - {len(github)} activities
  - {total_github_minutes} minutes total
  - Repos: {', '.join(set(a['repo'] for a in github))}

Meetings (Calendar):
  - {len(calendar)} events
  - {total_meeting_minutes} minutes total

Total Tracked Time: {total_slack_minutes + total_github_minutes + total_meeting_minutes} minutes
"""

    return summary


if __name__ == "__main__":
    # Start MCP server
    mcp.run()
