# PARAKH — Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| `main` branch | ✅ Actively maintained |

## Reporting a Vulnerability

If you discover a security issue (e.g. prompt injection bypasses the label text sandbox, medicine guard can be defeated), please **do not open a public GitHub issue**.

Instead, report privately via GitHub's **Security → Advisories → Report a vulnerability** feature on this repository.

We aim to respond within 72 hours and patch critical issues within 7 days.

## Scope

Issues of particular concern include:
- **Prompt injection** — label text causing PARAKH to execute instructions
- **Medicine guard bypass** — a medicine label being analysed rather than refused
- **Data leakage** — any path by which uploaded images could persist to disk
