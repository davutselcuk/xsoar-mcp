# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-04-15

### Added
- **MCP Prompts**: `investigate_incident`, `triage_phishing`, `hunt_ioc`,
  `daily_soc_briefing`
- **MCP Resources**: `xsoar://server/info`, `xsoar://incidents/recent`,
  `xsoar://incidents/open`
- **Read-only mode**: `XSOAR_READ_ONLY=true` disables all write tools
- **Debug logging**: `XSOAR_DEBUG=true` enables verbose log output
- **New tools**:
  - `execute_integration_command` — run any XSOAR integration command
  - `reopen_incident`
  - `get_incident_work_plan` — playbook task status
  - `create_indicator`
  - `list_integrations`
  - `list_incident_types`
- Retry logic for transient HTTP errors (5xx, 429, network errors)
- `smithery.yaml` for [smithery.ai](https://smithery.ai) registry
- GitHub Issue & PR templates
- Dependabot config
- Pre-commit config (ruff)
- PyPI release workflow (GitHub Actions)
- `py.typed` marker for PEP 561 type support
- Coverage reporting via `pytest-cov`

### Changed
- `XSOARClient` now uses a reusable `httpx.Client` (connection pooling)
- Server tools now use `XSOARClient` instead of duplicating HTTP logic
- Shared formatting helpers moved to `xsoar_mcp.utils`
- `XSOARError` is raised for HTTP failures with descriptive messages
- Tool docstrings now include query examples for better LLM usage

### Fixed
- Eliminated duplicate `_fmt_incident` between `server.py` and `xsoar_tools.py`

## [0.1.0] — 2026-04-10

### Added
- Initial release
- 13 MCP tools for XSOAR (incident, war room, playbook, indicator)
- Python CLI agent with 13 AI providers
- PowerShell agent with 13 AI providers
- Docker support
- GitHub Actions CI
- Unit tests
