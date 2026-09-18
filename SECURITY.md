# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could expose credentials, tokens, private endpoints, or user data.

For now, report security concerns privately to the repository owner through GitHub. Include reproduction steps, affected files, and the potential impact.

## Secrets

Restock Watch is designed so credentials stay outside committed configuration:

- `.env` and `.env.*` are ignored.
- Notification secrets are read from environment variables.
- Example configuration files contain no working credentials.
- n8n workflow templates in this repository contain no credential IDs, API keys, or tokens.

Before publishing a fork, review commit history for accidentally committed secrets. Removing a secret from the latest revision does not remove it from Git history.

## Deployment

Use HTTPS for outbound webhooks and protect inbound n8n webhooks with authentication before exposing them publicly. On shared systems, restrict access to environment files and runtime state.
