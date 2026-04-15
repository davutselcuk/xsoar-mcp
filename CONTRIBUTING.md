# Contributing to xsoar-mcp

Thanks for your interest! This project welcomes bug reports, feature requests,
and pull requests.

## Quick start

```bash
git clone https://github.com/davutselcuk/xsoar-mcp.git
cd xsoar-mcp
pip install -e ".[dev,agent]"
pre-commit install
```

## Running tests

```bash
pytest                       # all tests
pytest --cov                 # with coverage
pytest tests/test_server.py  # single file
```

## Linting

```bash
ruff check src/ tests/
ruff format src/ tests/      # auto-format
```

`pre-commit` will run these automatically on each commit.

## Project layout

```
src/xsoar_mcp/       # the MCP server package (server.py, client.py, utils.py)
examples/            # Python CLI agent (not installed as part of the package)
powershell/          # PowerShell agent (standalone)
tests/               # pytest tests
docs/                # installation guides
```

## Pull request workflow

1. Fork the repository
2. Create a branch: `git checkout -b feature/short-description`
3. Make your changes, add tests, update CHANGELOG.md under `## [Unreleased]`
4. Run `pytest` and `ruff check` — both must pass
5. Commit with a clear message (we use [Conventional Commits](https://www.conventionalcommits.org/) loosely: `feat:`, `fix:`, `docs:`, `test:`, `chore:`)
6. Open a PR against `main`

## Adding a new XSOAR tool

When adding a new MCP tool that calls XSOAR:

1. Add the underlying REST call as a method on `XSOARClient` in `src/xsoar_mcp/client.py`
2. Add an `@mcp.tool()` wrapper in `src/xsoar_mcp/server.py`
3. If the tool performs a write action, guard it with `_readonly_guard()`
4. Add a test in `tests/test_server.py` (use `_mock_client`) and
   `tests/test_client.py` for the raw API call
5. Document the tool in the "Available Tools" table in `README.md`

## Adding a new AI provider to the CLI agent

Both `examples/agent.py` (Python) and `powershell/xsoar-agent.ps1` have a
`PROVIDERS` registry. Add your entry with:

- `label`, `base_url`, `default_model`, `api_key_env_name`, `api_key_url`

If the provider is OpenAI-compatible (most are), no adapter code is needed.
For non-OpenAI APIs, add an adapter class (see `ClaudeAdapter` in `agent.py`).

## Reporting security issues

Please do **not** use public issues for security reports.
See [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the
MIT License.
