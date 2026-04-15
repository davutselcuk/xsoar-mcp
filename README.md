# xsoar-mcp

[![CI](https://github.com/davutselcuk/xsoar-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/davutselcuk/xsoar-mcp/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/xsoar-mcp.svg)](https://pypi.org/project/xsoar-mcp/)
[![Python Version](https://img.shields.io/pypi/pyversions/xsoar-mcp.svg)](https://pypi.org/project/xsoar-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-green)](https://modelcontextprotocol.io)
[![smithery](https://img.shields.io/badge/smithery-registered-blueviolet)](https://smithery.ai/server/xsoar-mcp)

A full-featured **MCP (Model Context Protocol) server** for **Palo Alto Cortex XSOAR**, enabling AI assistants (Claude, ChatGPT, Gemini, Llama, etc.) to manage security incidents, execute integration commands, run playbooks, and hunt indicators — all through natural language.

Includes a **Python CLI agent** and a **PowerShell agent** — both supporting **13 AI providers** out of the box.

Compatible with **XSOAR v6.x**. (v8 / Cortex XSIAM: most tools work; open an issue if you hit endpoint differences.)

---

## Features

**30 MCP Tools** covering the full XSOAR REST API:

- **Incidents** — search, get, create, update, close, reopen
- **War Room** — add notes, fetch entries, **execute any integration command**
- **Playbooks** — list, run, inspect task-level work plan, **complete/assign/annotate tasks**
- **Indicators (IOCs)** — search, get, create, edit, whitelist
- **Evidence Board** — create, search
- **XSOAR Lists** — get, save, list names (allow/block lists, lookup tables)
- **Automations** — search available scripts
- **Statistics** — query incident metrics by type/severity/owner
- **Audit Logs** — search the audit trail
- **Metadata** — list integrations, incident types, users, server info

**4 MCP Prompts** (pre-built investigation workflows)

- `/investigate_incident` — guided step-by-step triage
- `/triage_phishing` — batch triage of recent phishing
- `/hunt_ioc` — hunt one IOC across all incidents
- `/daily_soc_briefing` — generate today's SOC brief

**3 MCP Resources**

- `xsoar://server/info` — live server status
- `xsoar://incidents/recent` — last 20 incidents
- `xsoar://incidents/open` — currently open incidents

**Safety features**

- **Read-only mode** (`XSOAR_READ_ONLY=true`) — disables all write tools for safe exploration
- **Retry on transient errors** (5xx, 429, network)
- **Debug logging** (`XSOAR_DEBUG=true`)
- **Connection pooling** — single reusable HTTP client

---

## Installation

### Option 1 — uvx (no install required, MCP server only)

```bash
uvx xsoar-mcp
```

### Option 2 — pip

```bash
pip install xsoar-mcp           # MCP server only
pip install "xsoar-mcp[agent]"  # MCP server + Python CLI agent
```

### Option 3 — Docker

```bash
docker pull ghcr.io/davutselcuk/xsoar-mcp:latest
docker run -e XSOAR_URL=https://your-xsoar \
           -e XSOAR_API_KEY=your-key \
           ghcr.io/davutselcuk/xsoar-mcp:latest
```

### Option 4 — Smithery

```bash
npx -y @smithery/cli install xsoar-mcp
```

---

## Configuration

Required environment variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `XSOAR_URL` | ✅ | — | XSOAR server URL |
| `XSOAR_API_KEY` | ✅ | — | XSOAR API key |
| `XSOAR_VERIFY_SSL` | | `true` | Set `false` for self-signed certs |
| `XSOAR_READ_ONLY` | | `false` | Disable write tools (safe exploration) |
| `XSOAR_DEBUG` | | `false` | Verbose logging |

Copy `.env.example` to `.env` to get started:

```bash
cp .env.example .env
```

---

## Claude Desktop Setup

Add to your Claude Desktop config:

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
        "XSOAR_VERIFY_SSL": "true",
        "XSOAR_READ_ONLY": "false"
      }
    }
  }
}
```

See [`examples/claude_desktop_config.json`](examples/claude_desktop_config.json) for a complete example.

---

## Supported AI Providers (CLI / PowerShell agents)

Both agents support 13 providers. Select one interactively at startup or set `AI_PROVIDER` in `.env`.

| # | Provider | Key variable | Default model |
|---|---|---|---|
| 1 | **OpenAI** | `OPENAI_API_KEY` | `gpt-4o` |
| 2 | **Azure OpenAI** | `AZURE_API_KEY` | `gpt-4o` |
| 3 | **Claude (Anthropic)** | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| 4 | **Google Gemini** | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| 5 | **Groq** | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| 6 | **Mistral AI** | `MISTRAL_API_KEY` | `mistral-large-latest` |
| 7 | **Together AI** | `TOGETHER_API_KEY` | `meta-llama/Llama-3-70b-chat-hf` |
| 8 | **DeepSeek** | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| 9 | **Perplexity AI** | `PERPLEXITY_API_KEY` | `llama-3.1-sonar-large-128k-online` |
| 10 | **xAI (Grok)** | `XAI_API_KEY` | `grok-3-mini` |
| 11 | **Cohere** | `COHERE_API_KEY` | `command-r-plus` |
| 12 | **Ollama** *(local)* | — | `llama3.3` |
| 13 | **LM Studio** *(local)* | — | any loaded model |

---

## Python CLI Agent

```bash
pip install "xsoar-mcp[agent]"
cp .env.example .env   # fill in XSOAR_* and AI_* values
cd examples
python agent.py
```

---

## PowerShell Agent

No Python required. PowerShell 5.1+ or 7+.

```powershell
.\powershell\xsoar-agent.ps1
```

See [`docs/installation-powershell.md`](docs/installation-powershell.md) for detailed setup.

---

## Available Tools

| Tool | Description |
|---|---|
| `search_incidents` | Search with Lucene query |
| `get_incident` | Get full incident details |
| `create_incident` | Create a new incident |
| `update_incident` | Update severity/owner/status/custom fields |
| `close_incident` | Close an incident |
| `reopen_incident` | Reopen a closed incident |
| `add_war_room_entry` | Add a Markdown note |
| `get_war_room_entries` | Retrieve entries (notes, command output) |
| `execute_integration_command` | **Run any XSOAR integration command** (!ip, !vt-file, etc.) |
| `list_playbooks` | List available playbooks |
| `run_playbook_on_incident` | Trigger a playbook |
| `get_incident_work_plan` | View playbook task-level status |
| `search_indicators` | Search IOCs (IP, domain, hash, URL, CVE) |
| `get_indicator` | Get full IOC details |
| `create_indicator` | Create a new IOC |
| `list_integrations` | Discover available integrations |
| `list_incident_types` | List configured incident types |
| `list_users` | List XSOAR users |
| `get_server_info` | Verify connectivity + version |
| **Playbook Tasks** | |
| `complete_task` | Mark a playbook task as complete |
| `assign_task` | Assign a task to a user |
| `add_task_note` | Add a note to a task |
| **Indicators (extended)** | |
| `edit_indicator` | Change score/comment/expiration |
| `whitelist_indicators` | Mark IOCs as safe / false positive |
| **Evidence** | |
| `create_evidence` | Add evidence to an incident |
| `search_evidence` | Search evidence records |
| **XSOAR Lists** | |
| `get_list_names` | List all XSOAR lists |
| `get_list` | Get a named list (allow/block lists) |
| `save_list` | Create or update a list |
| **Discovery** | |
| `search_automations` | Search available scripts |
| `query_incident_statistics` | Aggregate incident stats |
| `search_audit_logs` | Query the audit trail |

## Available Resources

| URI | Returns |
|---|---|
| `xsoar://server/info` | Live server status + MCP mode |
| `xsoar://incidents/recent` | Last 20 incidents |
| `xsoar://incidents/open` | Currently open incidents |

## Available Prompts

| Prompt | Arguments | Purpose |
|---|---|---|
| `investigate_incident` | `incident_id` | Step-by-step guided triage |
| `triage_phishing` | — | Batch triage of recent phishing |
| `hunt_ioc` | `ioc_value` | Hunt an indicator across incidents |
| `daily_soc_briefing` | — | Generate today's SOC brief |

---

## Project Structure

```
xsoar-mcp/
├── src/xsoar_mcp/
│   ├── server.py         # MCP server (tools, resources, prompts)
│   ├── client.py         # XSOAR REST API client
│   └── utils.py          # shared formatting helpers
├── examples/
│   ├── agent.py          # Python CLI agent (13 AI providers)
│   ├── xsoar_tools.py    # tool definitions for CLI agent
│   └── claude_desktop_config.json
├── powershell/
│   └── xsoar-agent.ps1   # PowerShell agent (13 AI providers)
├── docs/
│   ├── installation-python.md
│   └── installation-powershell.md
├── tests/                # pytest suite
├── Dockerfile
├── smithery.yaml         # smithery.ai registry metadata
└── pyproject.toml
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports, feature requests, and PRs all welcome.

For security issues, please use the [private security advisory](https://github.com/davutselcuk/xsoar-mcp/security/advisories/new) — see [SECURITY.md](SECURITY.md).

---

## License

[MIT](LICENSE)

---

## Türkçe Özet

`xsoar-mcp`, Palo Alto Cortex XSOAR için **MCP (Model Context Protocol) sunucusudur**. AI asistanların (Claude, ChatGPT vs.) doğal dilde XSOAR üzerinde incident yönetmesine, entegrasyon komutu çalıştırmasına, playbook koşturmasına ve IOC araştırmasına olanak sağlar.

- 30 MCP tool, 4 prompt, 3 resource
- Python CLI + PowerShell agent (13 AI sağlayıcı)
- `XSOAR_READ_ONLY=true` ile yalnızca-okuma modu
- Docker, PyPI, Smithery üzerinden dağıtım
