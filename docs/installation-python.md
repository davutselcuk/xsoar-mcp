# Python Installation Guide

## Prerequisites

- Python 3.11 or higher
- A running Palo Alto Cortex XSOAR v6.x instance
- An XSOAR API key (Settings > API Keys > Generate New Key)

## Method 1 — uvx (Recommended)

No installation needed. Run directly with [uv](https://docs.astral.sh/uv/):

```bash
uvx xsoar-mcp
```

Configure via environment variables:

```bash
XSOAR_URL=https://your-xsoar XSOAR_API_KEY=your-key uvx xsoar-mcp
```

## Method 2 — pip install

```bash
pip install xsoar-mcp
xsoar-mcp
```

## Method 3 — Docker

```bash
docker pull ghcr.io/davutselcuk/xsoar-mcp:latest
docker run -e XSOAR_URL=https://your-xsoar \
           -e XSOAR_API_KEY=your-key \
           ghcr.io/davutselcuk/xsoar-mcp:latest
```

## Method 4 — Local clone

```bash
git clone https://github.com/davutselcuk/xsoar-mcp.git
cd xsoar-mcp
pip install -e ".[dev,agent]"
xsoar-mcp
```

## Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `XSOAR_URL` | Yes | — | XSOAR server URL |
| `XSOAR_API_KEY` | Yes | — | XSOAR API key |
| `XSOAR_VERIFY_SSL` | | `true` | `false` for self-signed certs |
| `XSOAR_READ_ONLY` | | `false` | Disable write tools for safe exploration |
| `XSOAR_DEBUG` | | `false` | Enable verbose logging |

## Running the Python CLI Agent

The CLI agent (`examples/agent.py`) supports 13 AI providers.

Install with agent dependencies:

```bash
pip install "xsoar-mcp[agent]"
```

Add AI settings to `.env`:

```ini
AI_PROVIDER=groq
AI_API_KEY=gsk_...
AI_MODEL=llama-3.3-70b-versatile
```

Run the agent:

```bash
cd examples
python agent.py
```

Or skip the menu by setting `AI_PROVIDER` in `.env`.

## Troubleshooting

**SSL certificate error:** Set `XSOAR_VERIFY_SSL=false` if your XSOAR uses a self-signed certificate.

**Connection refused:** Verify `XSOAR_URL` is reachable from your machine and the API key is valid.

**Import error:** Ensure you are using Python 3.11+ (`python --version`).

**Debug mode:** Set `XSOAR_DEBUG=true` to see detailed HTTP request/response logging.

**Read-only testing:** Set `XSOAR_READ_ONLY=true` to safely explore without modifying any data.
