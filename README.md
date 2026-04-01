# mcp-email-server

Stateless MCP server for AI agents to send and read email via SMTP/IMAP. Exposes both MCP tools and REST API endpoints. Designed for Kubernetes deployment.

## Features

- **10 MCP tools** for email operations (send, read, search, manage)
- **REST API** at `/api/v1/*` alongside MCP at `/mcp`
- **Multi-account** with per-account isolation (rate limits, domain allowlists)
- **Mail merge** (`mail_send_bulk`) with `{{variable}}` templates from JSON/CSV
- **Bearer token auth** on both MCP and REST endpoints
- **Stateless** — no database, deploys to Kubernetes

## Quick Start

```bash
# Install
uv sync

# Configure
cp .env.example .env
# Edit .env with your SMTP/IMAP credentials

# Run (stdio mode)
uv run mcp-mail

# Run (HTTP mode)
uv run mcp-mail --transport http
```

## MCP Tools

| Tool | Description |
|---|---|
| `mail_list_accounts` | List configured accounts (masked credentials) |
| `mail_send` | Send email with to/cc/bcc, HTML, attachments, reply threading |
| `mail_send_bulk` | Mail merge with `{{variable}}` templates |
| `mail_test_connection` | Test SMTP/IMAP connectivity |
| `mail_list` | List email metadata with filters and pagination |
| `mail_get` | Get full email content by ID (batch) |
| `mail_list_folders` | List IMAP folders with unread counts |
| `mail_move` | Move emails between folders |
| `mail_mark` | Mark emails read/unread/flagged |
| `mail_delete` | Permanently delete emails |

All tools accept an optional `account` parameter for multi-account support.

## REST API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/accounts` | List accounts |
| POST | `/api/v1/mail/send` | Send email |
| POST | `/api/v1/mail/send-bulk` | Bulk send with templates |
| GET | `/api/v1/mail/health` | Health check (unauthenticated, for K8s probes) |
| GET | `/api/v1/mail/test-connection` | Full SMTP/IMAP connectivity test |
| GET | `/api/v1/mail/messages` | List emails |
| GET | `/api/v1/mail/messages/{ids}` | Get email content |
| GET | `/api/v1/mail/folders` | List folders |
| POST | `/api/v1/mail/messages/move` | Move emails |
| PATCH | `/api/v1/mail/messages/mark` | Mark emails |
| DELETE | `/api/v1/mail/messages` | Delete emails |

## Configuration

All via environment variables. See [.env.example](.env.example) for full reference.

### Authentication

```env
AUTH_MODE=bearer                    # bearer | none
AUTH_BEARER_TOKEN=your-secret-token # required when AUTH_MODE=bearer
```

Set `AUTH_MODE=none` for local development (no token required).

### Multi-Account

Default account via `SMTP_*` / `IMAP_*` env vars. Additional accounts via `ACCOUNTS_JSON`:

```env
ACCOUNTS_JSON={"work":{"smtp":{"host":"smtp.office365.com","port":587,"username":"me@company.com","password":"...","start_tls":true,"from_address":"me@company.com"},"imap":{"host":"outlook.office365.com","port":993,"username":"me@company.com","password":"...","use_ssl":true},"from_address":"me@company.com","rate_limit_per_minute":30,"allowed_domains":["company.com"]}}
```

## Deployment

### Claude Desktop (stdio mode)

Configure your `.env` file in the project directory first, then add to Claude Desktop config:

```json
{
  "mcpServers": {
    "mcp-email-server": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/mcp-email-server", "mcp-mail"]
    }
  }
}
```

### Docker

```bash
docker build -t mcp-email-server .

# HTTP mode
docker run -p 8000:8000 --env-file .env mcp-email-server

# stdio mode
docker run -i --env-file .env mcp-email-server --transport stdio
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-email-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mcp-email-server
  template:
    metadata:
      labels:
        app: mcp-email-server
    spec:
      containers:
      - name: mcp-email-server
        image: mcp-email-server:latest
        args: ["--transport", "http"]
        ports: [{ containerPort: 8000 }]
        envFrom:
        - secretRef: { name: mcp-email-server-accounts }
        - secretRef: { name: mcp-email-server-auth }
        livenessProbe:
          httpGet: { path: /api/v1/mail/health, port: 8000 }
        readinessProbe:
          httpGet: { path: /api/v1/mail/health, port: 8000 }
```

## Development

```bash
uv sync --dev
uv run python -m pytest tests/ -v
```

## License

MIT
