# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately via GitHub Security Advisories
("Report a vulnerability" on the repository's **Security** tab). We aim to acknowledge
within a few business days. Please do not open a public issue for security reports.

## Scope & deployment notes

Atlas Core is a library; how you deploy it determines your security posture:

- **Multi-tenancy.** The `tenant` argument on `PgVectorStore` is a lightweight
  **filter**, not a security boundary. If you host untrusted tenants in one database,
  enable PostgreSQL **row-level security (RLS)** (or separate databases) — do not rely
  on the tenant filter alone.
- **Secrets.** Never hard-code DSNs or cloud credentials. Load them from your secret
  manager / environment. Nothing secret should live in the repo or image.
- **Network.** If your vector store is a managed DB, restrict its security group to
  the clients that need it — don't leave the port open to the world.
- **Untrusted content.** Node text is embedded and may be passed to an LLM for
  labels/narration; treat ingested content as untrusted input in your own pipeline.

## Supported versions

Fixes land on the latest `0.x` release line.
