# xsoar-mcp

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-green)](https://modelcontextprotocol.io)

An **MCP (Model Context Protocol) server** for **Palo Alto Cortex XSOAR**, enabling AI assistants (Claude, etc.) to manage security incidents, run playbooks, and investigate indicators directly from natural language.

Also includes a **Python CLI agent** and a **PowerShell agent** — both supporting **13 AI providers** out of the box.

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
docker build -t xsoar-mcp .
docker run -e XSOAR_URL=https://your-xsoar -e XSOAR_API_KEY=your-key xsoar-mcp
```

---

## Supported AI Providers

Both the Python agent and the PowerShell agent support **13 providers**. Select one interactively at startup or set `AI_PROVIDER` in your `.env`.

| # | Provider | Key variable | Default model | Get API key |
|---|---|---|---|---|
| 1 | **OpenAI** | `OPENAI_API_KEY` | `gpt-4o` | [platform.openai.com](https://platform.openai.com/api-keys) |
| 2 | **Azure OpenAI** | `AZURE_API_KEY` | `gpt-4o` | [portal.azure.com](https://portal.azure.com) |
| 3 | **Claude (Anthropic)** | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| 4 | **Google Gemini** | `GEMINI_API_KEY` | `gemini-2.0-flash` | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| 5 | **Groq** | `GROQ_API_KEY` | `llama-3.3-70b-versatile` | [console.groq.com](https://console.groq.com/keys) |
| 6 | **Mistral AI** | `MISTRAL_API_KEY` | `mistral-large-latest` | [console.mistral.ai](https://console.mistral.ai/api-keys) |
| 7 | **Together AI** | `TOGETHER_API_KEY` | `meta-llama/Llama-3-70b-chat-hf` | [api.together.ai](https://api.together.ai/settings/api-keys) |
| 8 | **DeepSeek** | `DEEPSEEK_API_KEY` | `deepseek-chat` | [platform.deepseek.com](https://platform.deepseek.com/api_keys) |
| 9 | **Perplexity AI** | `PERPLEXITY_API_KEY` | `llama-3.1-sonar-large-128k-online` | [perplexity.ai](https://www.perplexity.ai/settings/api) |
| 10 | **xAI (Grok)** | `XAI_API_KEY` | `grok-3-mini` | [console.x.ai](https://console.x.ai) |
| 11 | **Cohere** | `COHERE_API_KEY` | `command-r-plus` | [dashboard.cohere.com](https://dashboard.cohere.com/api-keys) |
| 12 | **Ollama** *(local)* | — | `llama3.3` | [ollama.com](https://ollama.com) |
| 13 | **LM Studio** *(local)* | — | any loaded model | [lmstudio.ai](https://lmstudio.ai) |

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Required for all configurations:

```ini
XSOAR_URL=https://your-xsoar-server.company.com
XSOAR_API_KEY=your-xsoar-api-key
XSOAR_VERIFY_SSL=true
```

Then add your AI provider credentials:

```ini
AI_PROVIDER=groq          # which provider to use
AI_API_KEY=gsk_...        # or use provider-specific var like GROQ_API_KEY
AI_MODEL=llama-3.3-70b-versatile   # optional, defaults are provided
```

---

## Claude Desktop Setup (MCP Server)

Add to your Claude Desktop configuration file:

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

See [`examples/claude_desktop_config.json`](examples/claude_desktop_config.json) for a complete example.

---

## Python CLI Agent

An interactive command-line agent. Supports all 13 providers.

```bash
pip install "xsoar-mcp[agent]"
cp .env.example .env   # fill in XSOAR_* and AI_* values
cd examples
python agent.py
```

At startup, choose your provider interactively:

```
Select AI provider:
  [ 1] OpenAI               (default model: gpt-4o)
  [ 2] Azure OpenAI         (default model: gpt-4o)
  [ 3] Claude               (default model: claude-sonnet-4-6)
  [ 4] Google Gemini        (default model: gemini-2.0-flash)
  [ 5] Groq                 (default model: llama-3.3-70b-versatile)
  [ 6] Mistral AI           (default model: mistral-large-latest)
  [ 7] Together AI          (default model: meta-llama/Llama-3-70b-chat-hf)
  [ 8] DeepSeek             (default model: deepseek-chat)
  [ 9] Perplexity AI        (default model: llama-3.1-sonar-large-128k-online)
  [10] xAI (Grok)           (default model: grok-3-mini)
  [11] Cohere               (default model: command-r-plus)
  [12] Ollama (local)       (default model: llama3.3)
  [13] LM Studio (local)    (default model: local-model)
```

Or skip the menu by setting `AI_PROVIDER` in `.env`.

---

## PowerShell Agent

A Windows-native agent with the same 13 providers. No Python required.

```powershell
# 1. Edit configuration variables at the top of the script
# 2. Run:
.\powershell\xsoar-agent.ps1
```

At startup:

```
Select AI provider (or press Enter for default: openai):
  [ 1] OpenAI
  [ 2] Azure OpenAI (APIM)
  [ 3] Claude (Anthropic)
  [ 4] Google Gemini
  [ 5] Groq
  [ 6] Mistral AI
  [ 7] Together AI
  [ 8] DeepSeek
  [ 9] Perplexity AI
  [10] xAI (Grok)
  [11] Cohere
  [12] Ollama (local)
  [13] LM Studio (local)
```

**Requirements:** PowerShell 5.1+ or PowerShell 7+. No additional packages needed.

See [`docs/installation-powershell.md`](docs/installation-powershell.md) for detailed setup.

---

## Available Tools (MCP Server)

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
│   ├── agent.py         # Python CLI agent (13 AI providers)
│   ├── xsoar_tools.py   # OpenAI function-calling tool definitions
│   └── claude_desktop_config.json
├── powershell/
│   └── xsoar-agent.ps1  # PowerShell agent (13 AI providers)
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
