"""
MCP Client for Timetracker

Connects to external MCP servers to aggregate time tracking data
from various sources (Slack, GitHub, Calendar, etc.)
"""
import asyncio
from datetime import datetime
from typing import Optional, Any
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from core.database_protocol import DatabaseProtocol


class TimeTrackerMCPClient:
    """
    MCP Client that connects to external services and imports activities
    into the Timetracker database
    """

    def __init__(self, database: DatabaseProtocol):
        """
        Initialize MCP client

        Args:
            database: Database instance to store imported activities
        """
        self.database = database
        self.sessions: dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, server_name: str, command: str, args: list[str] = None):
        """
        Connect to an MCP server

        Args:
            server_name: Name identifier for the server
            command: Command to start the server (e.g., 'python', 'node')
            args: Arguments for the command (e.g., ['mcp_server_demo.py'])
        """
        if args is None:
            args = []

        # Create server parameters
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=None
        )

        # Connect to server
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )

        read_stream, write_stream = stdio_transport

        # Create client session
        session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        # Initialize session
        await session.initialize()

        # Store session
        self.sessions[server_name] = session

        print(f"[OK] Connected to MCP server: {server_name}")

    async def list_tools(self, server_name: str) -> list[dict]:
        """
        List available tools from a server

        Args:
            server_name: Name of the server

        Returns:
            List of tool definitions
        """
        if server_name not in self.sessions:
            raise ValueError(f"Not connected to server: {server_name}")

        session = self.sessions[server_name]
        tools_response = await session.list_tools()

        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
            for tool in tools_response.tools
        ]

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any] = None
    ) -> Any:
        """
        Call a tool on an MCP server

        Args:
            server_name: Name of the server
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if server_name not in self.sessions:
            raise ValueError(f"Not connected to server: {server_name}")

        if arguments is None:
            arguments = {}

        session = self.sessions[server_name]
        result = await session.call_tool(tool_name, arguments)

        return result

    async def import_activities_from_server(
        self,
        server_name: str,
        date: Optional[str] = None,
        project_name: Optional[str] = None
    ) -> int:
        """
        Import activities from an MCP server into the database

        Args:
            server_name: Name of the server to import from
            date: Date to import (YYYY-MM-DD format, default: today)
            project_name: Optional project name to assign activities to

        Returns:
            Number of activities imported
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Get or create project
        project_id = None
        if project_name:
            projects = self.database.get_projects()
            project = next((p for p in projects if p["name"] == project_name), None)

            if not project:
                project_id = self.database.create_project(project_name)
            else:
                project_id = project["id"]

        # Try to get activities from different tools
        imported_count = 0

        # Check available tools
        tools = await self.list_tools(server_name)
        tool_names = [t["name"] for t in tools]

        # Import Slack activities
        if "get_slack_activities" in tool_names:
            result = await self.call_tool(
                server_name, "get_slack_activities", {"date": date}
            )
            for activity in result.content[0].text if hasattr(result.content[0], 'text') else []:
                # Parse activity data
                if isinstance(activity, dict):
                    self._import_activity(activity, "Slack", project_id)
                    imported_count += 1

        # Import GitHub activities
        if "get_github_activities" in tool_names:
            result = await self.call_tool(
                server_name, "get_github_activities", {"date": date}
            )
            # Similar import logic
            imported_count += len(result.content) if hasattr(result, 'content') else 0

        # Import Calendar events
        if "get_calendar_events" in tool_names:
            result = await self.call_tool(
                server_name, "get_calendar_events", {"date": date}
            )
            # Similar import logic
            imported_count += len(result.content) if hasattr(result, 'content') else 0

        return imported_count

    def _import_activity(
        self, activity_data: dict, source: str, project_id: Optional[int] = None
    ):
        """
        Import a single activity into the database

        Args:
            activity_data: Activity data from MCP server
            source: Source name (e.g., 'Slack', 'GitHub')
            project_id: Optional project ID to assign
        """
        # Parse timestamps
        start_time = datetime.fromisoformat(activity_data.get("start_time"))
        end_time = datetime.fromisoformat(activity_data.get("end_time"))

        # Generate window title
        if "channel" in activity_data:
            title = f"{activity_data['channel']} - Slack"
        elif "repo" in activity_data:
            title = f"{activity_data['repo']} - {activity_data.get('type', 'GitHub')}"
        elif "title" in activity_data:
            title = activity_data["title"]
        else:
            title = f"{source} Activity"

        # Save activity
        activity_id = self.database.save_activity(
            app_name=f"{source}.exe",
            window_title=title,
            start_time=start_time,
            end_time=end_time,
            is_idle=False,
            process_path=None
        )

        # Assign to project if provided
        if project_id and activity_id:
            self.database.assign_activity_to_project(activity_id, project_id)

    async def get_summary(self, server_name: str, date: str) -> str:
        """
        Get activity summary from server

        Args:
            server_name: Name of the server
            date: Date in YYYY-MM-DD format

        Returns:
            Summary text
        """
        result = await self.call_tool(
            server_name, "get_daily_summary", {"date": date}
        )

        # Extract text from result
        if hasattr(result, 'content') and result.content:
            return result.content[0].text

        return str(result)

    async def close(self):
        """Close all connections"""
        await self.exit_stack.aclose()
        self.sessions.clear()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
