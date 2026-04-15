# Security Policy

## Supported Versions

Security fixes are applied to the latest released version.

| Version | Supported |
| ------- | --------- |
| 0.2.x   | ✅        |
| < 0.2   | ❌        |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in `xsoar-mcp`, we ask that you report it
privately so we can address it before public disclosure.

**How to report:**

1. **GitHub Security Advisory (preferred):**
   Open a [private advisory](https://github.com/davutselcuk/xsoar-mcp/security/advisories/new)
   via the repository Security tab.

2. **Email:** If GitHub is unavailable to you, email the maintainer directly
   (see repository owner profile).

Please include:

- A description of the vulnerability and its impact
- Steps to reproduce (proof-of-concept if possible)
- The affected version(s)
- Any known mitigations

## What to Expect

- **Acknowledgement:** within 72 hours of your report
- **Initial assessment:** within 7 days
- **Fix and disclosure:** coordinated with you, typically within 30 days for
  high-severity issues

We will credit you in the advisory unless you prefer to remain anonymous.

## Scope

Issues we consider in-scope:

- Credential leakage (API keys, tokens)
- Injection / SSRF via user input routed to XSOAR
- Authentication bypass or privilege escalation against the MCP server
- Remote code execution via maliciously crafted tool arguments
- Supply-chain issues in dependencies

Out-of-scope:

- Vulnerabilities in XSOAR itself (report to Palo Alto Networks)
- Social-engineering of AI providers
- Denial of service from abusing `execute_integration_command` against a
  legitimate XSOAR instance (this is an operator configuration concern)

## Hardening Recommendations

When running `xsoar-mcp` in production:

- Use `XSOAR_READ_ONLY=true` for demos / exploratory agents
- Rotate `XSOAR_API_KEY` regularly
- Never commit `.env` files
- Pin the package version in production deployments
- Keep XSOAR itself patched to the latest v6 / v8 release

Thank you for helping keep `xsoar-mcp` and its users secure.
