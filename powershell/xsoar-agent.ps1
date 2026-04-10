# ============================================================
#  XSOAR AI Agent - PowerShell
#  Requirements: Windows PowerShell 5.1+ or PowerShell 7+
#  Usage: .\xsoar-agent.ps1
# ============================================================

# UTF-8 console encoding (required for proper output rendering)
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::InputEncoding  = [System.Text.Encoding]::UTF8
    $OutputEncoding           = [System.Text.Encoding]::UTF8
    chcp 65001 | Out-Null
} catch {}

# ============================================================
#  CONFIGURATION — fill in only the providers you want to use
# ============================================================
$XSOAR_URL     = "https://your-xsoar-server.company.com"
$XSOAR_API_KEY = "YOUR_XSOAR_API_KEY_HERE"
$XSOAR_SSL     = $false   # $true if your certificate is trusted

# Default provider (can also be selected interactively at startup):
# openai | azure | claude | gemini | groq | mistral | together |
# deepseek | perplexity | xai | cohere | ollama | lmstudio
$AI_PROVIDER = "openai"

# --- OpenAI ---                       https://platform.openai.com/api-keys
$OPENAI_API_KEY = "sk-..."
$OPENAI_MODEL   = "gpt-4o"

# --- Azure OpenAI (APIM) ---
$AZURE_API_KEY    = "YOUR_APIM_KEY_HERE"
$AZURE_ENDPOINT   = "https://your-apim.azure-api.net/your-deployment"
$AZURE_DEPLOYMENT = "gpt-4o"
$AZURE_API_VER    = "2024-02-01"

# --- Claude (Anthropic) ---           https://console.anthropic.com/settings/keys
$CLAUDE_API_KEY = "sk-ant-..."
$CLAUDE_MODEL   = "claude-sonnet-4-6"   # claude-opus-4-6 | claude-haiku-4-5

# --- Google Gemini ---                https://aistudio.google.com/app/apikey
$GEMINI_API_KEY = "AIza..."
$GEMINI_MODEL   = "gemini-2.0-flash"

# --- Groq ---                         https://console.groq.com/keys
$GROQ_API_KEY = "gsk_..."
$GROQ_MODEL   = "llama-3.3-70b-versatile"

# --- Mistral AI ---                   https://console.mistral.ai/api-keys
$MISTRAL_API_KEY = "..."
$MISTRAL_MODEL   = "mistral-large-latest"

# --- Together AI ---                  https://api.together.ai/settings/api-keys
$TOGETHER_API_KEY = "..."
$TOGETHER_MODEL   = "meta-llama/Llama-3-70b-chat-hf"

# --- DeepSeek ---                     https://platform.deepseek.com/api_keys
$DEEPSEEK_API_KEY = "sk-..."
$DEEPSEEK_MODEL   = "deepseek-chat"

# --- Perplexity AI ---                https://www.perplexity.ai/settings/api
$PERPLEXITY_API_KEY = "pplx-..."
$PERPLEXITY_MODEL   = "llama-3.1-sonar-large-128k-online"

# --- xAI (Grok) ---                   https://console.x.ai
$XAI_API_KEY = "xai-..."
$XAI_MODEL   = "grok-3-mini"

# --- Cohere ---                       https://dashboard.cohere.com/api-keys
$COHERE_API_KEY = "..."
$COHERE_MODEL   = "command-r-plus"

# --- Ollama (local) ---               https://ollama.com
$OLLAMA_URL   = "http://localhost:11434"
$OLLAMA_MODEL = "llama3.3"

# --- LM Studio (local) ---            https://lmstudio.ai
$LMSTUDIO_URL   = "http://localhost:1234"
$LMSTUDIO_MODEL = "local-model-name"
# ============================================================

# SSL bypass (for self-signed XSOAR certificates)
if (-not $XSOAR_SSL) {
    if ($PSVersionTable.PSVersion.Major -ge 7) {
        $script:SkipSSL = @{ SkipCertificateCheck = $true }
    } else {
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
        $script:SkipSSL = @{}
    }
} else {
    $script:SkipSSL = @{}
}

# -- XSOAR HELPER FUNCTIONS ----------------------------------

function Invoke-XSOAR {
    param($Method, $Path, $Body = $null)
    $headers = @{
        "Authorization" = $XSOAR_API_KEY
        "Content-Type"  = "application/json"
        "Accept"        = "application/json"
    }
    $params = @{
        Method  = $Method
        Uri     = "$XSOAR_URL$Path"
        Headers = $headers
    }
    foreach ($k in $script:SkipSSL.Keys) { $params[$k] = $script:SkipSSL[$k] }
    if ($Body) {
        $params.Body = ($Body | ConvertTo-Json -Depth 10)
    }
    try {
        return Invoke-RestMethod @params
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        throw "XSOAR API error ($code): $($_.Exception.Message)"
    }
}

$SEV  = @{0="Unknown"; 1="Low"; 2="Medium"; 3="High"; 4="Critical"}
$STAT = @{0="Pending"; 1="Active"; 2="Closed"; 3="Archived"}

function Format-Incident($i) {
    return @{
        id           = $i.id
        name         = $i.name
        type         = $i.type
        severity     = $SEV[[int]$i.severity]
        status       = $STAT[[int]$i.status]
        owner        = $i.owner
        occurred     = $i.occurred
        details      = if ($i.details) { $i.details.Substring(0, [Math]::Min(300, $i.details.Length)) } else { "" }
        playbook     = $i.playbookId
        close_reason = $i.closeReason
    }
}

# -- TOOL DEFINITIONS (OpenAI function-calling format) --------

$TOOLS = @(
    @{ type="function"; function=@{
        name="get_server_info"
        description="Test connectivity to XSOAR and return version info."
        parameters=@{ type="object"; properties=@{}; required=@() }
    }},
    @{ type="function"; function=@{
        name="search_incidents"
        description="Search XSOAR incidents. Example query: 'type:Phishing AND severity:3'"
        parameters=@{
            type="object"
            properties=@{
                query=@{ type="string"; description="Lucene query, empty returns all" }
                size=@{ type="integer"; description="Max results (default 20)" }
                page=@{ type="integer"; description="Page number, starting from 0" }
            }
            required=@()
        }
    }},
    @{ type="function"; function=@{
        name="get_incident"
        description="Get all details for a specific incident ID."
        parameters=@{
            type="object"
            properties=@{ incident_id=@{ type="string"; description="XSOAR incident ID" } }
            required=@("incident_id")
        }
    }},
    @{ type="function"; function=@{
        name="create_incident"
        description="Create a new XSOAR incident."
        parameters=@{
            type="object"
            properties=@{
                name=@{ type="string"; description="Incident name (required)" }
                type=@{ type="string"; description="Type: Phishing, Malware, Unclassified, etc." }
                severity=@{ type="integer"; description="Severity: 0=Unknown 1=Low 2=Medium 3=High 4=Critical" }
                details=@{ type="string"; description="Description" }
                owner=@{ type="string"; description="Assigned username" }
                playbook_id=@{ type="string"; description="Playbook ID to auto-start" }
            }
            required=@("name")
        }
    }},
    @{ type="function"; function=@{
        name="update_incident"
        description="Update an existing incident (severity, owner, status, etc.)."
        parameters=@{
            type="object"
            properties=@{
                incident_id=@{ type="string"; description="Incident ID to update" }
                severity=@{ type="integer"; description="New severity 0-4" }
                owner=@{ type="string"; description="New assigned user" }
                status=@{ type="integer"; description="Status: 0=Pending 1=Active 2=Closed 3=Archived" }
                details=@{ type="string"; description="New description" }
            }
            required=@("incident_id")
        }
    }},
    @{ type="function"; function=@{
        name="close_incident"
        description="Close an incident."
        parameters=@{
            type="object"
            properties=@{
                incident_id=@{ type="string"; description="Incident ID to close" }
                close_reason=@{ type="string"; description="Close reason: Resolved, False Positive, Duplicate, etc." }
                close_notes=@{ type="string"; description="Closing notes" }
            }
            required=@("incident_id")
        }
    }},
    @{ type="function"; function=@{
        name="add_war_room_entry"
        description="Add a note or comment to an incident's War Room."
        parameters=@{
            type="object"
            properties=@{
                incident_id=@{ type="string"; description="Target incident ID" }
                content=@{ type="string"; description="Content to add (supports Markdown)" }
            }
            required=@("incident_id","content")
        }
    }},
    @{ type="function"; function=@{
        name="search_indicators"
        description="Search threat indicators (IOCs): IPs, domains, file hashes, URLs."
        parameters=@{
            type="object"
            properties=@{
                query=@{ type="string"; description="Search value, e.g. 8.8.8.8 or malware.com" }
                ioc_type=@{ type="string"; description="Type filter: IP, Domain, File, URL, CVE, etc." }
                size=@{ type="integer"; description="Max results" }
            }
            required=@("query")
        }
    }},
    @{ type="function"; function=@{
        name="list_playbooks"
        description="List available XSOAR playbooks."
        parameters=@{ type="object"; properties=@{}; required=@() }
    }},
    @{ type="function"; function=@{
        name="run_playbook_on_incident"
        description="Run a specific playbook on an incident."
        parameters=@{
            type="object"
            properties=@{
                incident_id=@{ type="string"; description="Target incident ID" }
                playbook_id=@{ type="string"; description="Playbook ID to run" }
            }
            required=@("incident_id","playbook_id")
        }
    }}
)

# -- TOOL EXECUTOR --------------------------------------------

function Invoke-Tool {
    param($Name, $ToolArgs)
    try {
        switch ($Name) {

            "get_server_info" {
                $r = Invoke-XSOAR GET "/about"
                return @{ connected=$true; version=$r.demistoVersion; build=$r.buildNum }
            }

            "search_incidents" {
                $body = @{ filter=@{
                    query = if ($ToolArgs.query) { $ToolArgs.query } else { "" }
                    size  = if ($ToolArgs.size)  { [int]$ToolArgs.size } else { 20 }
                    page  = if ($ToolArgs.page)  { [int]$ToolArgs.page } else { 0 }
                    sort  = @(@{ field="occurred"; asc=$false })
                }}
                $r = Invoke-XSOAR POST "/incidents/search" $body
                $list = if ($r.data) { $r.data } else { @() }
                return @{
                    total    = $r.total
                    returned = $list.Count
                    incidents = @($list | ForEach-Object { Format-Incident $_ })
                }
            }

            "get_incident" {
                $r = Invoke-XSOAR GET "/incident/load/$($ToolArgs.incident_id)"
                return Format-Incident $r
            }

            "create_incident" {
                $body = @{
                    name     = $ToolArgs.name
                    type     = if ($ToolArgs.type)     { $ToolArgs.type }     else { "Unclassified" }
                    severity = if ($ToolArgs.severity) { [int]$ToolArgs.severity } else { 1 }
                    details  = if ($ToolArgs.details)  { $ToolArgs.details }  else { "" }
                }
                if ($ToolArgs.owner)       { $body.owner      = $ToolArgs.owner }
                if ($ToolArgs.playbook_id) { $body.playbookId = $ToolArgs.playbook_id }
                $r = Invoke-XSOAR POST "/incident" $body
                return @{ created=$true; id=$r.id; name=$r.name }
            }

            "update_incident" {
                $body = @{ id=$ToolArgs.incident_id; version=-1 }
                if ($null -ne $ToolArgs.severity) { $body.severity = [int]$ToolArgs.severity }
                if ($ToolArgs.owner)              { $body.owner    = $ToolArgs.owner }
                if ($null -ne $ToolArgs.status)   { $body.status   = [int]$ToolArgs.status }
                if ($ToolArgs.details)            { $body.details  = $ToolArgs.details }
                Invoke-XSOAR POST "/incident" $body | Out-Null
                return @{ updated=$true; id=$ToolArgs.incident_id }
            }

            "close_incident" {
                $body = @{
                    id          = $ToolArgs.incident_id
                    version     = -1
                    closeReason = if ($ToolArgs.close_reason) { $ToolArgs.close_reason } else { "Resolved" }
                    closeNotes  = if ($ToolArgs.close_notes)  { $ToolArgs.close_notes }  else { "" }
                }
                Invoke-XSOAR POST "/incident/close" $body | Out-Null
                return @{ closed=$true; id=$ToolArgs.incident_id }
            }

            "add_war_room_entry" {
                $body = @{
                    investigationId = $ToolArgs.incident_id
                    data            = $ToolArgs.content
                    markdown        = $true
                }
                Invoke-XSOAR POST "/entry" $body | Out-Null
                return @{ added=$true; incident_id=$ToolArgs.incident_id }
            }

            "search_indicators" {
                $body = @{
                    query = $ToolArgs.query
                    size  = if ($ToolArgs.size) { [int]$ToolArgs.size } else { 20 }
                    page  = 0
                }
                if ($ToolArgs.ioc_type) { $body.type = $ToolArgs.ioc_type }
                $r    = Invoke-XSOAR POST "/indicators/search" $body
                $list = if ($r.iocObjects) { $r.iocObjects } else { @() }
                return @{
                    total      = $r.total
                    indicators = @($list | ForEach-Object {
                        @{ id=$_.id; value=$_.value; type=$_.indicator_type; score=$_.score }
                    })
                }
            }

            "list_playbooks" {
                $r    = Invoke-XSOAR POST "/playbook/search" @{ page=0; size=100 }
                $list = if ($r.playbooks) { $r.playbooks } elseif ($r -is [array]) { $r } else { @() }
                return @{
                    count     = $list.Count
                    playbooks = @($list | ForEach-Object {
                        @{ id=$_.id; name=$_.name; description=$_.description }
                    })
                }
            }

            "run_playbook_on_incident" {
                Invoke-XSOAR POST "/incident/playbook/$($ToolArgs.incident_id)/$($ToolArgs.playbook_id)" `
                    @{ incidentId=$ToolArgs.incident_id; version=-1 } | Out-Null
                return @{ started=$true; incident_id=$ToolArgs.incident_id; playbook_id=$ToolArgs.playbook_id }
            }

            default { return @{ error="Unknown tool: $Name" } }
        }
    } catch {
        return @{ error=$_.Exception.Message }
    }
}

# -- AI API CALL ----------------------------------------------
# Claude uses a different API format; these helpers convert to/from OpenAI
# format so the main agent loop stays unchanged for all providers.

function Convert-ToolsForClaude($Tools) {
    # OpenAI tools → Anthropic tools (input_schema instead of parameters)
    return @($Tools | ForEach-Object {
        @{
            name         = $_.function.name
            description  = $_.function.description
            input_schema = $_.function.parameters
        }
    })
}

function Convert-MessagesForClaude($Messages) {
    # Returns @{ system=string; messages=array }
    # Converts tool role and tool_calls to Anthropic format
    $system   = ""
    $converted = [System.Collections.ArrayList]@()

    foreach ($msg in $Messages) {
        if ($msg.role -eq "system") {
            $system = $msg.content
            continue
        }

        if ($msg.role -eq "tool") {
            # Group consecutive tool results into a single user message
            $last = if ($converted.Count -gt 0) { $converted[$converted.Count - 1] } else { $null }
            $toolBlock = @{ type="tool_result"; tool_use_id=$msg.tool_call_id; content=$msg.content }
            if ($last -and $last.role -eq "user" -and $last.content -is [array]) {
                $last.content += $toolBlock
            } else {
                $converted.Add(@{ role="user"; content=@($toolBlock) }) | Out-Null
            }
            continue
        }

        if ($msg.role -eq "assistant" -and $msg.tool_calls) {
            $content = [System.Collections.ArrayList]@()
            if ($msg.content) { $content.Add(@{ type="text"; text=$msg.content }) | Out-Null }
            foreach ($tc in $msg.tool_calls) {
                $input = $tc.function.arguments | ConvertFrom-Json -ErrorAction SilentlyContinue
                if (-not $input) { $input = @{} }
                $content.Add(@{ type="tool_use"; id=$tc.id; name=$tc.function.name; input=$input }) | Out-Null
            }
            $converted.Add(@{ role="assistant"; content=$content.ToArray() }) | Out-Null
            continue
        }

        $converted.Add(@{ role=$msg.role; content=$msg.content }) | Out-Null
    }

    return @{ system=$system; messages=$converted.ToArray() }
}

function Convert-ClaudeResponseToOpenAI($Response) {
    # Normalize Anthropic response → OpenAI-like shape so main loop is unchanged
    $text       = ""
    $tool_calls = [System.Collections.ArrayList]@()

    foreach ($block in $Response.content) {
        if ($block.type -eq "text") { $text = $block.text }
        elseif ($block.type -eq "tool_use") {
            $tool_calls.Add(@{
                id       = $block.id
                type     = "function"
                function = @{
                    name      = $block.name
                    arguments = ($block.input | ConvertTo-Json -Depth 10 -Compress)
                }
            }) | Out-Null
        }
    }

    $msg = @{ role="assistant" }
    if ($text)                    { $msg.content    = $text }
    if ($tool_calls.Count -gt 0) { $msg.tool_calls = $tool_calls.ToArray() }

    return @{ choices = @(@{ message = $msg }) }
}

# -------------------------------------------------------------

function Invoke-AI {
    param($Messages)

    # ── Claude (Anthropic native API) ─────────────────────────
    if ($AI_PROVIDER -eq "claude") {
        $converted = Convert-MessagesForClaude $Messages
        $body = @{
            model      = $CLAUDE_MODEL
            max_tokens = 4096
            system     = $converted.system
            messages   = $converted.messages
            tools      = Convert-ToolsForClaude $TOOLS
        }
        $headers = @{
            "x-api-key"         = $CLAUDE_API_KEY
            "anthropic-version" = "2023-06-01"
            "Content-Type"      = "application/json"
        }
        $uri = "https://api.anthropic.com/v1/messages"

        $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 20))
        $params = @{
            Method          = "POST"
            Uri             = $uri
            Headers         = $headers
            Body            = $bodyBytes
            ContentType     = "application/json; charset=utf-8"
            UseBasicParsing = $true
        }
        if ($PSVersionTable.PSVersion.Major -ge 7) { $params.SkipCertificateCheck = $true }
        try {
            $raw        = Invoke-WebRequest @params
            $text       = [System.Text.Encoding]::UTF8.GetString($raw.RawContentStream.ToArray())
            $claudeResp = $text | ConvertFrom-Json
            return Convert-ClaudeResponseToOpenAI $claudeResp
        } catch {
            $code    = $_.Exception.Response.StatusCode.value__
            $errBody = ""
            try { if ($_.ErrorDetails.Message) { $errBody = $_.ErrorDetails.Message } } catch {}
            Write-Host "  [DEBUG] URL: $uri" -ForegroundColor DarkCyan
            throw "Claude API error ($code): $($_.Exception.Message) $errBody"
        }
    }

    # ── Azure OpenAI (APIM — custom header + api-version) ─────
    if ($AI_PROVIDER -eq "azure") {
        $uri = "$AZURE_ENDPOINT/openai/deployments/$AZURE_DEPLOYMENT/chat/completions"
        if ($AZURE_API_VER -and ($uri -notmatch "api-version=")) {
            $sep = if ($uri.Contains("?")) { "&" } else { "?" }
            $uri = "$uri${sep}api-version=$AZURE_API_VER"
        }
        $headers = @{ "api-key"="$AZURE_API_KEY"; "Content-Type"="application/json" }
        $body    = @{ messages=$Messages; tools=$TOOLS; tool_choice="auto" }
    }
    else {
        # ── All other OpenAI-compatible providers ──────────────
        $urlMap = @{
            "openai"     = "https://api.openai.com/v1/chat/completions"
            "gemini"     = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            "groq"       = "https://api.groq.com/openai/v1/chat/completions"
            "mistral"    = "https://api.mistral.ai/v1/chat/completions"
            "together"   = "https://api.together.xyz/v1/chat/completions"
            "deepseek"   = "https://api.deepseek.com/v1/chat/completions"
            "perplexity" = "https://api.perplexity.ai/chat/completions"
            "xai"        = "https://api.x.ai/v1/chat/completions"
            "cohere"     = "https://api.cohere.com/compatibility/v1/chat/completions"
            "ollama"     = "$OLLAMA_URL/v1/chat/completions"
            "lmstudio"   = "$LMSTUDIO_URL/v1/chat/completions"
        }
        $keyMap = @{
            "openai"     = $OPENAI_API_KEY
            "gemini"     = $GEMINI_API_KEY
            "groq"       = $GROQ_API_KEY
            "mistral"    = $MISTRAL_API_KEY
            "together"   = $TOGETHER_API_KEY
            "deepseek"   = $DEEPSEEK_API_KEY
            "perplexity" = $PERPLEXITY_API_KEY
            "xai"        = $XAI_API_KEY
            "cohere"     = $COHERE_API_KEY
            "ollama"     = "ollama"
            "lmstudio"   = "lm-studio"
        }
        $modelMap = @{
            "openai"     = $OPENAI_MODEL
            "gemini"     = $GEMINI_MODEL
            "groq"       = $GROQ_MODEL
            "mistral"    = $MISTRAL_MODEL
            "together"   = $TOGETHER_MODEL
            "deepseek"   = $DEEPSEEK_MODEL
            "perplexity" = $PERPLEXITY_MODEL
            "xai"        = $XAI_MODEL
            "cohere"     = $COHERE_MODEL
            "ollama"     = $OLLAMA_MODEL
            "lmstudio"   = $LMSTUDIO_MODEL
        }
        $uri     = $urlMap[$AI_PROVIDER]
        $headers = @{ "Authorization"="Bearer $($keyMap[$AI_PROVIDER])"; "Content-Type"="application/json" }
        $body    = @{ model=$modelMap[$AI_PROVIDER]; messages=$Messages; tools=$TOOLS; tool_choice="auto" }
    }

    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 20))
    $params = @{
        Method          = "POST"
        Uri             = $uri
        Headers         = $headers
        Body            = $bodyBytes
        ContentType     = "application/json; charset=utf-8"
        UseBasicParsing = $true
    }
    if ($PSVersionTable.PSVersion.Major -ge 7) { $params.SkipCertificateCheck = $true }
    try {
        $raw  = Invoke-WebRequest @params
        $text = [System.Text.Encoding]::UTF8.GetString($raw.RawContentStream.ToArray())
        return $text | ConvertFrom-Json
    } catch {
        $code    = $_.Exception.Response.StatusCode.value__
        $errBody = ""
        try { if ($_.ErrorDetails.Message) { $errBody = $_.ErrorDetails.Message } } catch {}
        Write-Host "  [DEBUG] URL: $uri" -ForegroundColor DarkCyan
        throw "AI API error ($code): $($_.Exception.Message) $errBody"
    }
}

# -- MAIN AGENT LOOP ------------------------------------------

$systemPrompt = "You are a security operations assistant managing Palo Alto Cortex XSOAR. " +
                "Use the provided tools for incident management, IOC investigation, and playbook execution. " +
                "For irreversible actions like closing incidents, always ask the user for confirmation first."

$messages = [System.Collections.ArrayList]@(
    @{ role="system"; content=$systemPrompt }
)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  XSOAR AI Agent (PowerShell)" -ForegroundColor Cyan
Write-Host "  Type 'exit' or press Ctrl+C to quit" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# --- Interactive provider selection ---
Write-Host ""
Write-Host "Select AI provider (or press Enter for default: $AI_PROVIDER):" -ForegroundColor Yellow
Write-Host "  [1]  OpenAI" -ForegroundColor Gray
Write-Host "  [2]  Azure OpenAI (APIM)" -ForegroundColor Gray
Write-Host "  [3]  Claude (Anthropic)" -ForegroundColor Gray
Write-Host "  [4]  Google Gemini" -ForegroundColor Gray
Write-Host "  [5]  Groq" -ForegroundColor Gray
Write-Host "  [6]  Mistral AI" -ForegroundColor Gray
Write-Host "  [7]  Together AI" -ForegroundColor Gray
Write-Host "  [8]  DeepSeek" -ForegroundColor Gray
Write-Host "  [9]  Perplexity AI" -ForegroundColor Gray
Write-Host "  [10] xAI (Grok)" -ForegroundColor Gray
Write-Host "  [11] Cohere" -ForegroundColor Gray
Write-Host "  [12] Ollama (local)" -ForegroundColor Gray
Write-Host "  [13] LM Studio (local)" -ForegroundColor Gray
Write-Host "Choice: " -ForegroundColor Yellow -NoNewline
$providerChoice = Read-Host
switch ($providerChoice.Trim()) {
    "1"           { $AI_PROVIDER = "openai" }
    "openai"      { $AI_PROVIDER = "openai" }
    "2"           { $AI_PROVIDER = "azure" }
    "azure"       { $AI_PROVIDER = "azure" }
    "3"           { $AI_PROVIDER = "claude" }
    "claude"      { $AI_PROVIDER = "claude" }
    "4"           { $AI_PROVIDER = "gemini" }
    "gemini"      { $AI_PROVIDER = "gemini" }
    "5"           { $AI_PROVIDER = "groq" }
    "groq"        { $AI_PROVIDER = "groq" }
    "6"           { $AI_PROVIDER = "mistral" }
    "mistral"     { $AI_PROVIDER = "mistral" }
    "7"           { $AI_PROVIDER = "together" }
    "together"    { $AI_PROVIDER = "together" }
    "8"           { $AI_PROVIDER = "deepseek" }
    "deepseek"    { $AI_PROVIDER = "deepseek" }
    "9"           { $AI_PROVIDER = "perplexity" }
    "perplexity"  { $AI_PROVIDER = "perplexity" }
    "10"          { $AI_PROVIDER = "xai" }
    "xai"         { $AI_PROVIDER = "xai" }
    "11"          { $AI_PROVIDER = "cohere" }
    "cohere"      { $AI_PROVIDER = "cohere" }
    "12"          { $AI_PROVIDER = "ollama" }
    "ollama"      { $AI_PROVIDER = "ollama" }
    "13"          { $AI_PROVIDER = "lmstudio" }
    "lmstudio"    { $AI_PROVIDER = "lmstudio" }
    default       { <# keep $AI_PROVIDER as configured #> }
}
Write-Host ("  -> Using: {0}" -f $AI_PROVIDER) -ForegroundColor DarkCyan

while ($true) {
    Write-Host ""
    Write-Host "You: " -ForegroundColor Green -NoNewline
    $userInput = Read-Host

    if ([string]::IsNullOrWhiteSpace($userInput)) { continue }
    if ($userInput -in @("exit", "quit")) {
        Write-Host "Goodbye!" -ForegroundColor Yellow
        break
    }

    $messages.Add(@{ role="user"; content=$userInput }) | Out-Null

    # Agentic loop: continue while AI is calling tools
    while ($true) {
        Write-Host "  (thinking...) " -ForegroundColor DarkGray -NoNewline
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            $response = Invoke-AI $messages
        } catch {
            $sw.Stop()
            Write-Host ""
            Write-Host "ERROR: $_" -ForegroundColor Red
            break
        }
        $sw.Stop()
        Write-Host ("[{0:N1}s]" -f $sw.Elapsed.TotalSeconds) -ForegroundColor DarkGray

        # Validate response format
        if (-not $response -or -not $response.choices -or $response.choices.Count -eq 0) {
            Write-Host "ERROR: AI returned an unexpected response format." -ForegroundColor Red
            Write-Host "Raw response:" -ForegroundColor Yellow
            $response | ConvertTo-Json -Depth 10 | Write-Host -ForegroundColor DarkGray
            break
        }

        $choice  = $response.choices[0]
        $msg     = $choice.message
        $msgHash = @{ role="assistant" }

        if ($msg.content)    { $msgHash.content    = $msg.content }
        if ($msg.tool_calls) { $msgHash.tool_calls = $msg.tool_calls }
        $messages.Add($msgHash) | Out-Null

        # No tool calls → respond to user
        if (-not $msg.tool_calls) {
            Write-Host ""
            Write-Host "AI: " -ForegroundColor Magenta -NoNewline
            Write-Host $msg.content
            break
        }

        # Process tool calls
        foreach ($tc in $msg.tool_calls) {
            $toolName       = $tc.function.name
            $toolArgsParsed = $tc.function.arguments | ConvertFrom-Json -ErrorAction SilentlyContinue
            if (-not $toolArgsParsed) { $toolArgsParsed = New-Object PSObject }

            Write-Host "  [Tool: $toolName]" -ForegroundColor DarkYellow

            $result     = Invoke-Tool $toolName $toolArgsParsed
            $resultJson = $result | ConvertTo-Json -Depth 10

            $messages.Add(@{
                role         = "tool"
                tool_call_id = $tc.id
                content      = $resultJson
            }) | Out-Null
        }
        # Loop continues → AI evaluates results
    }
}
