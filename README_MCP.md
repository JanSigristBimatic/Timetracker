# MCP Client Integration - POC

## Was ist MCP?

**Model Context Protocol (MCP)** ist ein offener Standard von Anthropic, der es AI-Assistenten ermöglicht, mit externen Systemen zu kommunizieren. Für Timetracker bedeutet das:

- Automatischer Import von Aktivitäten aus Slack, GitHub, Calendar, etc.
- AI-gesteuerte Zeiterfassung ohne manuelle Eingabe
- Integration mit bestehenden MCP-Servern

## Architektur

```
┌─────────────────────────────────────────────┐
│         Timetracker (MCP Client)            │
│  ┌────────────────────────────────────┐     │
│  │  TimeTrackerMCPClient              │     │
│  │  - connect_to_server()             │     │
│  │  - call_tool()                     │     │
│  │  - import_activities()             │     │
│  └────────────────────────────────────┘     │
└──────────────┬──────────────────────────────┘
               │ MCP Protocol
               │
    ┌──────────┴───────────┬─────────────────┐
    │                      │                 │
┌───▼────────────┐  ┌─────▼──────────┐  ┌──▼──────────┐
│ Slack MCP      │  │ GitHub MCP     │  │ Calendar    │
│ Server         │  │ Server         │  │ MCP Server  │
└────────────────┘  └────────────────┘  └─────────────┘
```

## Installation

```bash
pip install "mcp[cli]"
```

## POC Demo

### 1. Demo MCP Server starten

Der Demo-Server simuliert Slack, GitHub und Calendar:

```bash
python mcp_server_demo.py
```

### 2. MCP Client Demo ausführen

```bash
python mcp_demo.py
```

## Verwendung im Code

```python
from core.database import Database
from mcp.client import TimeTrackerMCPClient

async def import_from_slack():
    db = Database()

    async with TimeTrackerMCPClient(db) as client:
        # Verbinde zu Slack MCP Server
        await client.connect_to_server(
            server_name="slack",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-slack"]
        )

        # Importiere heutige Aktivitäten
        count = await client.import_activities_from_server(
            server_name="slack",
            project_name="Communication"
        )

        print(f"Imported {count} activities")
```

## Verfügbare MCP Server

### Offizielle MCP Server von Anthropic:

- **Slack**: `@modelcontextprotocol/server-slack`
- **GitHub**: `@modelcontextprotocol/server-github`
- **Google Drive**: `@modelcontextprotocol/server-google-drive`
- **Postgres**: `@modelcontextprotocol/server-postgres`
- **Puppeteer**: `@modelcontextprotocol/server-puppeteer`

### Custom Server erstellen:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MyService")

@mcp.tool()
def get_activities(date: str) -> list[dict]:
    """Get activities for a date"""
    # Your logic here
    return [...]
```

## Features des POC

### ✅ Implementiert

- ✅ Verbindung zu MCP Servern über stdio
- ✅ Tool Discovery (list_tools)
- ✅ Tool Aufruf mit Parametern
- ✅ Integration mit Timetracker Database
- ✅ Demo Server mit Slack/GitHub/Calendar Simulation

### 🚧 Nächste Schritte

- Parse MCP response formats korrekt
- Automatischer Import scheduler
- Conflict resolution für überlappende Aktivitäten
- Support für SSE und HTTP transports
- OAuth integration für echte Services
- GUI Integration (Import-Button im Timetracker)

## Beispiel-Workflow

1. **Morgens**: Timetracker startet automatisch
2. **Tagsüber**: MCP Client importiert alle 30min Aktivitäten von:
   - Slack (Kommunikation)
   - GitHub (Entwicklung)
   - Calendar (Meetings)
   - Jira (Tickets)
3. **Abends**: Automatische Projektzuordnung via AI
4. **Export**: Stundenrapport generieren

## Integration mit AI

Der MCP Client ermöglicht es, einen AI-Agenten (wie Claude) zu verwenden:

```python
# AI Agent kann automatisch entscheiden:
# - Welche MCP Server genutzt werden
# - Wie Aktivitäten kategorisiert werden
# - Welchen Projekten sie zugeordnet werden
# - Wann Reports generiert werden sollen
```

## Troubleshooting

### Server startet nicht
```bash
# Prüfe ob MCP installiert ist
py -m pip show mcp

# Teste Server manuell
py mcp_server_demo.py
```

### Client kann nicht verbinden
- Stelle sicher, dass der Server läuft
- Prüfe den command und args Parameter
- Windows: Nutze "py" statt "python"

## Links

- [MCP Specification](https://modelcontextprotocol.io/)
- [Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Available MCP Servers](https://github.com/modelcontextprotocol/servers)
- [Anthropic Blog](https://www.anthropic.com/news/model-context-protocol)

## Lizenz

MIT
