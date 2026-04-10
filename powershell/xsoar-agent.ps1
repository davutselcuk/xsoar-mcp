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
#  CONFIGURATION — edit these values
# ============================================================
$XSOAR_API_KEY = "YOUR_XSOAR_API_KEY_HERE"

# Which AI provider to use: "azure", "local", or "claude"
$AI_PROVIDER = "azure"

# --- Azure APIM (if AI_PROVIDER = "azure") ---
$APIM_API_KEY  = "YOUR_APIM_API_KEY_HERE"

# --- Local LLM (if AI_PROVIDER = "local") ---
$LOCAL_URL     = "http://localhost:1234/v1/chat/completions"  # LM Studio / Ollama default
$LOCAL_API_KEY = "lm-studio"                                  # not required by most local LLMs
$LOCAL_MODEL   = "your-local-model-name"                      # model loaded in LM Studio / Ollama

# --- Claude / Anthropic (if AI_PROVIDER = "claude") ---
$CLAUDE_API_KEY = "YOUR_ANTHROPIC_API_KEY_HERE"               # https://console.anthropic.com
$CLAUDE_MODEL   = "claude-sonnet-4-6"                         # or claude-opus-4-6, claude-haiku-4-5
# ============================================================

# --- Edit below only if needed ---
$XSOAR_URL        = "https://your-xsoar-server.company.com"
$XSOAR_SSL        = $false
$APIM_ENDPOINT    = "https://your-apim.azure-api.net/your-deployment"
$APIM_DEPLOYMENT  = "gpt-4o"
$APIM_API_VERSION = "2024-02-01"
$APIM_AUTH_HEADER = "api-key"
$APIM_URL = "$APIM_ENDPOINT/openai/deployments/$APIM_DEPLOYMENT/chat/completions"
# ---------------------------------

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

# -- CLAUDE API HELPERS ---------------------------------------
# Claude uses a different API format; these convert to/from OpenAI format
# so the main agent loop stays unchanged.

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

    # ── Claude (Anthropic) ────────────────────────────────────
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
            $raw      = Invoke-WebRequest @params
            $text     = [System.Text.Encoding]::UTF8.GetString($raw.RawContentStream.ToArray())
            $claudeResp = $text | ConvertFrom-Json
            return Convert-ClaudeResponseToOpenAI $claudeResp
        } catch {
            $code    = $_.Exception.Response.StatusCode.value__
            $errBody = ""
            try { if ($_.ErrorDetails.Message) { $errBody = $_.ErrorDetails.Message } } catch {}
            Write-Host ""
            Write-Host "  [DEBUG] URL: $uri" -ForegroundColor DarkCyan
            throw "Claude API error ($code): $($_.Exception.Message) $errBody"
        }
    }

    # ── OpenAI-compatible (Azure APIM / Local LLM) ────────────
    $body = @{
        messages    = $Messages
        tools       = $TOOLS
        tool_choice = "auto"
    }

    if ($AI_PROVIDER -eq "local") {
        $body.model = $LOCAL_MODEL
        $headers = @{
            "Authorization" = "Bearer $LOCAL_API_KEY"
            "Content-Type"  = "application/json"
        }
        $uri = $LOCAL_URL
    }
    else {
        # Azure APIM
        $headers = @{
            $APIM_AUTH_HEADER = $APIM_API_KEY
            "Content-Type"    = "application/json"
        }
        if ($APIM_API_VERSION -and ($APIM_URL -notmatch "api-version=")) {
            $sep = if ($APIM_URL.Contains("?")) { "&" } else { "?" }
            $uri = "$APIM_URL${sep}api-version=$APIM_API_VERSION"
        } else {
            $uri = $APIM_URL
        }
    }

    $jsonBody  = $body | ConvertTo-Json -Depth 20
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($jsonBody)

    $params = @{
        Method          = "POST"
        Uri             = $uri
        Headers         = $headers
        Body            = $bodyBytes
        ContentType     = "application/json; charset=utf-8"
        UseBasicParsing = $true
    }
    if ($PSVersionTable.PSVersion.Major -ge 7) {
        $params.SkipCertificateCheck = $true
    }
    try {
        $raw  = Invoke-WebRequest @params
        $text = [System.Text.Encoding]::UTF8.GetString($raw.RawContentStream.ToArray())
        return $text | ConvertFrom-Json
    } catch {
        $code    = $_.Exception.Response.StatusCode.value__
        $errBody = ""
        try { if ($_.ErrorDetails.Message) { $errBody = $_.ErrorDetails.Message } } catch {}
        Write-Host ""
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

# --- AI provider selection (interactive) ---
Write-Host ""
Write-Host "Select AI provider:" -ForegroundColor Yellow
Write-Host "  [1] Azure APIM (default)" -ForegroundColor Gray
Write-Host "  [2] Local LLM  (LM Studio / Ollama)" -ForegroundColor Gray
Write-Host "  [3] Claude     (Anthropic)" -ForegroundColor Gray
Write-Host "Choice (1/2/3, Enter = 1): " -ForegroundColor Yellow -NoNewline
$providerChoice = Read-Host
switch ($providerChoice.Trim()) {
    "2"      { $AI_PROVIDER = "local" }
    "local"  { $AI_PROVIDER = "local" }
    "3"      { $AI_PROVIDER = "claude" }
    "claude" { $AI_PROVIDER = "claude" }
    "azure"  { $AI_PROVIDER = "azure" }
    default  { $AI_PROVIDER = "azure" }
}
Write-Host ("  -> AI provider: {0}" -f $AI_PROVIDER) -ForegroundColor DarkCyan

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
