# Python Installation Guide

## Prerequisites

- Python 3.11 or higher
- A running Palo Alto Cortex XSOAR v6.x instance
- An XSOAR API key (Settings → API Keys → Generate New Key)

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

## Method 3 — Local clone

```bash
git clone https://github.com/YOUR_USERNAME/xsoar-mcp.git
cd xsoar-mcp
pip install -e .
xsoar-mcp
```

## Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Then edit `.env`:

```ini
XSOAR_URL=https://your-xsoar-server.company.com
XSOAR_API_KEY=your-api-key-here
XSOAR_VERIFY_SSL=true
```

## Running the Python CLI Agent

The CLI agent (`examples/agent.py`) requires an OpenAI-compatible LLM endpoint.

Install with agent dependencies:

```bash
pip install "xsoar-mcp[agent]"
```

Add AI settings to `.env`:

```ini
AI_BASE_URL=http://localhost:1234/v1
AI_API_KEY=lm-studio
AI_MODEL=llama-3.3-70b
```

Run the agent:

```bash
cd examples
python agent.py
```

## Troubleshooting

**SSL certificate error:** Set `XSOAR_VERIFY_SSL=false` if your XSOAR uses a self-signed certificate.

**Connection refused:** Verify `XSOAR_URL` is reachable from your machine and the API key is valid.

**Import error:** Ensure you are using Python 3.11+ (`python --version`).
