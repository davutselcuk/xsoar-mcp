# xsoar-mcp

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-green)](https://modelcontextprotocol.io)

An **MCP (Model Context Protocol) server** for **Palo Alto Cortex XSOAR**, enabling AI assistants (Claude, etc.) to manage security incidents, run playbooks, and investigate indicators directly from natural language.

Also includes a **Python CLI agent** and a **PowerShell agent** — both using OpenAI-compatible APIs to connect any LLM to XSOAR.

Compatible with **XSOAR v6.x**.

---

## Features

- **Incident Management** — search, create, update, and close incidents
- **War Room** — add notes and retrieve entries from incident investigations
- **Playbook Execution** — list and trigger playbooks on incidents
- **Indicator (IOC) Search** — query IPs, domains, file hashes, URLs, CVEs
- **Server Status** — verify connectivity and XSOAR version
- **User Management** — list users for incident assignment

---

## Installation

### Option 1 — uvx (no install required)

```bash
uvx xsoar-mcp
```

### Option 2 — pip

```bash
pip install xsoar-mcp
xsoar-mcp
```

### Option 3 — Docker

```bash
docker build -t xsoar-mcp .
docker run -e XSOAR_URL=https://your-xsoar -e XSOAR_API_KEY=your-key xsoar-mcp
```

---

## Configuration

Set the following environment variables (or create a `.env` file):

| Variable | Required | Description |
|---|---|---|
| `XSOAR_URL` | Yes | XSOAR server URL, e.g. `https://xsoar.company.com` |
| `XSOAR_API_KEY` | Yes | XSOAR API key (Settings → API Keys → Generate) |
| `XSOAR_VERIFY_SSL` | No | Set to `false` for self-signed certificates (default: `true`) |

For the Python CLI agent, also set:

| Variable | Required | Description |
|---|---|---|
| `AI_BASE_URL` | Yes | OpenAI-compatible API base URL |
| `AI_API_KEY` | Yes | AI API key |
| `AI_MODEL` | Yes | Model name (e.g. `gpt-4o`, `llama-3.3-70b`) |

Copy `.env.example` to get started:

```bash
cp .env.example .env
```

---

## Claude Desktop Setup

Add the following to your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "xsoar": {
      "command": "uvx",
      "args": ["xsoar-mcp"],
      "env": {
        "XSOAR_URL": "https://your-xsoar-server.company.com",
        "XSOAR_API_KEY": "your-api-key-here",
        "XSOAR_VERIFY_SSL": "true"
      }
    }
  }
}
```

Or using a local clone:

```json
{
  "mcpServers": {
    "xsoar": {
      "command": "python",
      "args": ["/path/to/xsoar-mcp/src/xsoar_mcp/server.py"],
      "env": {
        "XSOAR_URL": "https://your-xsoar-server.company.com",
        "XSOAR_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

See [`examples/claude_desktop_config.json`](examples/claude_desktop_config.json) for a complete example.

---

## Python CLI Agent

An interactive command-line agent that uses any OpenAI-compatible LLM:

```bash
pip install "xsoar-mcp[agent]"
cp .env.example .env  # fill in your values
cd examples
python agent.py
```

Example session:

```
You: List all critical incidents from today
AI: [Tool: search_incidents] ...
    Found 3 critical incidents: ...

You: Add a war room note to incident 1234 saying investigation started
AI: [Tool: add_war_room_entry] ...
    Note added successfully.
```

---

## PowerShell Agent

A Windows-native agent supporting **Azure APIM** and **local LLMs** (LM Studio, Ollama). No Python required.

```powershell
# Edit configuration at the top of the script, then run:
.\powershell\xsoar-agent.ps1
```

At startup, select your AI provider:

```
Select AI provider:
  [1] Azure APIM (default)
  [2] Local LLM  (LM Studio / Ollama)
```

See [`docs/installation-powershell.md`](docs/installation-powershell.md) for detailed setup instructions.

---

## Available Tools

| Tool | Description |
|---|---|
| `search_incidents` | Search incidents with Lucene query, pagination, and sorting |
| `get_incident` | Get full details of a specific incident |
| `create_incident` | Create a new incident with type, severity, owner, and playbook |
| `update_incident` | Update severity, owner, status, or custom fields |
| `close_incident` | Close an incident with reason and notes |
| `add_war_room_entry` | Add a Markdown note to an incident's War Room |
| `get_war_room_entries` | Retrieve War Room entries (notes, commands, results) |
| `list_playbooks` | List available playbooks with name and description |
| `run_playbook_on_incident` | Trigger a playbook on a specific incident |
| `search_indicators` | Search IOCs: IPs, domains, hashes, URLs, CVEs |
| `get_indicator` | Get full details of a specific IOC |
| `get_server_info` | Verify connectivity and get XSOAR version |
| `list_users` | List users for incident assignment |

---

## Project Structure

```
xsoar-mcp/
├── src/xsoar_mcp/
│   ├── server.py        # MCP server (FastMCP, 13 tools)
│   └── client.py        # XSOAR REST API client
├── examples/
│   ├── agent.py         # Python CLI agent
│   ├── xsoar_tools.py   # OpenAI function-calling tool definitions
│   └── claude_desktop_config.json
├── powershell/
│   └── xsoar-agent.ps1  # PowerShell agent (Azure APIM + Local LLM)
├── docs/
│   ├── installation-python.md
│   └── installation-powershell.md
└── pyproject.toml
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes and verify: `pip install -e ".[dev]" && ruff check src/`
4. Open a pull request

---

## License

[MIT](LICENSE)
