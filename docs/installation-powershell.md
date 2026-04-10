# PowerShell Agent Installation Guide

## Prerequisites

- Windows PowerShell 5.1+ **or** PowerShell 7+
- A running Palo Alto Cortex XSOAR v6.x instance
- An XSOAR API key (Settings → API Keys → Generate New Key)
- An API key for at least one of the 13 supported AI providers (see table below)

No Python or additional packages required.

## Supported AI Providers

| # | Provider | Where to get API key |
|---|---|---|
| 1 | OpenAI | [platform.openai.com](https://platform.openai.com/api-keys) |
| 2 | Azure OpenAI (APIM) | [portal.azure.com](https://portal.azure.com) |
| 3 | Claude (Anthropic) | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| 4 | Google Gemini | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| 5 | Groq | [console.groq.com](https://console.groq.com/keys) |
| 6 | Mistral AI | [console.mistral.ai](https://console.mistral.ai/api-keys) |
| 7 | Together AI | [api.together.ai](https://api.together.ai/settings/api-keys) |
| 8 | DeepSeek | [platform.deepseek.com](https://platform.deepseek.com/api_keys) |
| 9 | Perplexity AI | [perplexity.ai](https://www.perplexity.ai/settings/api) |
| 10 | xAI (Grok) | [console.x.ai](https://console.x.ai) |
| 11 | Cohere | [dashboard.cohere.com](https://dashboard.cohere.com/api-keys) |
| 12 | Ollama (local) | [ollama.com](https://ollama.com) — no key needed |
| 13 | LM Studio (local) | [lmstudio.ai](https://lmstudio.ai) — no key needed |

---

## Setup (Recommended: .env file)

The agent reads a `.env` file from the same directory, so you don't need to edit the script itself.

**1. Copy the example file:**

```powershell
Copy-Item .env.example .env
```

**2. Edit `.env` with your values:**

```ini
# XSOAR
XSOAR_URL=https://your-xsoar-server.company.com
XSOAR_API_KEY=your-xsoar-api-key
XSOAR_SSL=false

# Choose your provider
AI_PROVIDER=groq
GROQ_API_KEY=gsk_...
```

**3. Run the script:**

```powershell
.\powershell\xsoar-agent.ps1
```

**4. Select your provider at startup (or press Enter to use the default):**

```
Select AI provider (or press Enter for default: groq):
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

---

## Alternative: Edit Variables Directly

If you prefer not to use a `.env` file, open `powershell\xsoar-agent.ps1` and fill in the configuration section at the top:

```powershell
$XSOAR_URL     = "https://your-xsoar-server.company.com"
$XSOAR_API_KEY = "your-xsoar-api-key"

$AI_PROVIDER   = "groq"
$GROQ_API_KEY  = "gsk_..."
$GROQ_MODEL    = "llama-3.3-70b-versatile"
```

---

## Provider-Specific Notes

### Azure OpenAI (APIM)
```ini
AI_PROVIDER=azure
AZURE_API_KEY=your-apim-key
AZURE_ENDPOINT=https://your-apim.azure-api.net/your-deployment
AZURE_DEPLOYMENT=gpt-4o
AZURE_API_VER=2024-02-01
```

### Claude (Anthropic)
```ini
AI_PROVIDER=claude
CLAUDE_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6
```
Claude uses a different API format internally; the agent handles the conversion automatically.

### Ollama / LM Studio (local)
```ini
AI_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.3
```
No API key required. Start your local server before running the agent.

---

## Execution Policy

If PowerShell blocks the script, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## Troubleshooting

| Error | Fix |
|---|---|
| SSL errors connecting to XSOAR | Set `XSOAR_SSL=false` in `.env` |
| AI API 401 Unauthorized | Check your API key and provider selection |
| `.env` not loaded | Make sure `.env` is in the same directory as the script |
| Unicode display issues | Run `chcp 65001` before starting the script |
