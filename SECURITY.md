# Security policy

## Reporting a vulnerability

If you've found a security issue in `methods-mcp`, please report it privately:

- **Email**: flynnlachendro@hotmail.co.uk
- **Subject prefix**: `[methods-mcp security]`
- **GitHub Security Advisory**: <https://github.com/FlynnLachendro/methods-mcp/security/advisories/new> (preferred — gives us a private channel and a CVE if appropriate)

Please do **not** open a public GitHub issue for security reports.

I aim to acknowledge security reports within 48 hours and ship a fix or mitigation as soon as possible.

## Supported versions

`methods-mcp` is currently in alpha (0.1.x). Only the **latest released version** receives security fixes. If you're pinning a specific version, plan to upgrade as new releases ship.

| Version | Supported |
|---------|-----------|
| 0.1.x latest | ✅ |
| Earlier 0.1.x | ❌ (pin & upgrade) |

## What this server does (and doesn't)

- **Network egress** is limited to: `export.arxiv.org`, `ar5iv.labs.arxiv.org`, `arxiv.org`, `api.github.com`, `paperswithcode.com`, `api.anthropic.com`. No telemetry, no analytics.
- **Secrets**: the server reads `ANTHROPIC_API_KEY` and optionally `GITHUB_TOKEN` from env vars. They are sent only to the corresponding APIs and never logged or persisted.
- **Filesystem**: no writes outside of standard Python interpreter behaviour.
- **Code execution**: none on user input. No `eval`, `exec`, `pickle.loads`, or `subprocess` on tool inputs.

See the **Security & limitations** section of the [README](README.md) for the full surface description and known limitations (prompt injection in paper text, reproducibility-as-heuristic, intended transport).
