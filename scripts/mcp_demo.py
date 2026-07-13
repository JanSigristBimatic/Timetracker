"""
MCP Client Demo / Proof of Concept

Demonstrates how the Timetracker can connect to external MCP servers
and automatically import activities from various sources.

Usage:
    python mcp_demo.py
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.database import Database
from mcp_client.client import TimeTrackerMCPClient
from datetime import datetime


async def demo_mcp_client():
    """Run MCP client demo"""

    print("=" * 60)
    print("TimeTracker MCP Client - Proof of Concept")
    print("=" * 60)
    print()

    # Initialize database
    print("[DATABASE] Initializing database...")
    db = Database()
    print("[OK] Database ready")
    print()

    # Create MCP client
    print("[MCP] Creating MCP client...")
    async with TimeTrackerMCPClient(db) as client:
        print("[OK] MCP client created")
        print()

        # Connect to demo server
        print("[CONNECT] Connecting to demo MCP server...")
        print("          (This simulates Slack, GitHub, Calendar integrations)")
        print()

        try:
            await client.connect_to_server(
                server_name="communication_tracker",
                command="py",
                args=["mcp_server_demo.py"]
            )
        except Exception as e:
            print(f"[ERROR] Failed to connect to server: {e}")
            print()
            print("Make sure mcp_server_demo.py is in the current directory")
            return

        print()

        # List available tools
        print("[TOOLS] Available tools from server:")
        tools = await client.list_tools("communication_tracker")
        for tool in tools:
            print(f"        - {tool['name']}: {tool['description']}")
        print()

        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")

        # Get summary
        print(f"[SUMMARY] Getting activity summary for {today}...")
        print()
        try:
            summary = await client.get_summary("communication_tracker", today)
            print(summary)
        except Exception as e:
            print(f"          Note: Summary not available ({e})")
        print()

        # Call individual tools
        print("[SLACK] Fetching Slack activities...")
        try:
            slack_result = await client.call_tool(
                "communication_tracker",
                "get_slack_activities",
                {"date": today}
            )
            print(f"        Result: {slack_result}")
        except Exception as e:
            print(f"        Error: {e}")
        print()

        print("[GITHUB] Fetching GitHub activities...")
        try:
            github_result = await client.call_tool(
                "communication_tracker",
                "get_github_activities",
                {"date": today}
            )
            print(f"         Result: {github_result}")
        except Exception as e:
            print(f"         Error: {e}")
        print()

        print("[CALENDAR] Fetching Calendar events...")
        try:
            calendar_result = await client.call_tool(
                "communication_tracker",
                "get_calendar_events",
                {"date": today}
            )
            print(f"           Result: {calendar_result}")
        except Exception as e:
            print(f"           Error: {e}")
        print()

        # Import activities (if implemented)
        print("[IMPORT] Importing activities into Timetracker database...")
        try:
            # Create a project for imported activities
            project_id = db.create_project("MCP Imported Activities", "#9b59b6")
            print(f"         [OK] Created project: MCP Imported Activities (ID: {project_id})")

            # Note: Full import requires parsing the MCP response format
            print("         Note: Full import functionality requires MCP response parsing")
            print("         This POC demonstrates the connection and tool calling")
        except Exception as e:
            print(f"         Error: {e}")
        print()

        print("=" * 60)
        print("Demo completed!")
        print()
        print("What this POC demonstrates:")
        print("  [OK] Connection to external MCP servers")
        print("  [OK] Discovery of available tools")
        print("  [OK] Calling tools with parameters")
        print("  [OK] Integration with Timetracker database")
        print()
        print("Next steps:")
        print("  - Connect to real MCP servers (Slack, GitHub, etc.)")
        print("  - Parse MCP response formats correctly")
        print("  - Implement automatic periodic imports")
        print("  - Add conflict resolution for overlapping activities")
        print("=" * 60)

    # Close database
    db.close()


def main():
    """Main entry point"""
    try:
        asyncio.run(demo_mcp_client())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
