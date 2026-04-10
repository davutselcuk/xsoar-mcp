# PowerShell Agent Installation Guide

## Prerequisites

- Windows PowerShell 5.1+ **or** PowerShell 7+
- A running Palo Alto Cortex XSOAR v6.x instance
- An XSOAR API key (Settings → API Keys → Generate New Key)
- An AI endpoint: Azure APIM (Azure OpenAI) **or** a local LLM (LM Studio, Ollama)

No Python or additional packages required.

## Setup

1. Clone or download the repository.

2. Open `powershell\xsoar-agent.ps1` in a text editor and fill in the configuration section at the top:

```powershell
# ============================================================
#  CONFIGURATION — edit these values
# ============================================================
$XSOAR_API_KEY = "YOUR_XSOAR_API_KEY_HERE"

$AI_PROVIDER = "azure"   # "azure" or "local"

# --- Azure APIM ---
$APIM_API_KEY  = "YOUR_APIM_API_KEY_HERE"

# --- Local LLM ---
$LOCAL_URL     = "http://localhost:1234/v1/chat/completions"
$LOCAL_API_KEY = "lm-studio"
$LOCAL_MODEL   = "your-local-model-name"

# --- XSOAR server ---
$XSOAR_URL = "https://your-xsoar-server.company.com"
$XSOAR_SSL = $false   # set $true if your certificate is trusted
```

3. Run the script:

```powershell
.\powershell\xsoar-agent.ps1
```

4. At startup, select your AI provider:

```
Select AI provider:
  [1] Azure APIM (default)
  [2] Local LLM  (LM Studio / Ollama)
```

## Using with Azure OpenAI via APIM

Set the following variables:

```powershell
$APIM_ENDPOINT    = "https://your-apim.azure-api.net/your-deployment"
$APIM_DEPLOYMENT  = "gpt-4o"
$APIM_API_VERSION = "2024-02-01"
$APIM_AUTH_HEADER = "api-key"
$APIM_API_KEY     = "YOUR_APIM_KEY"
```

## Using with Local LLM (LM Studio / Ollama)

Start your local LLM server, then set:

```powershell
$LOCAL_URL    = "http://localhost:1234/v1/chat/completions"  # LM Studio default
$LOCAL_MODEL  = "llama-3.3-70b"                             # model you have loaded
$LOCAL_API_KEY = "lm-studio"                                # arbitrary string, required by header
```

Select `[2] Local LLM` when the agent starts.

## Execution Policy

If PowerShell blocks the script, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## Troubleshooting

**SSL errors connecting to XSOAR:** Set `$XSOAR_SSL = $false` to bypass certificate validation.

**AI API 401 error:** Double-check your API key and endpoint URL.

**Turkish/Unicode display issues:** The script sets UTF-8 encoding automatically. If characters still appear wrong, run `chcp 65001` manually before starting the script.
