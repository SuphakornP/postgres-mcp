# PostgreSQL MCP Server

A **FastMCP-based** read-only PostgreSQL MCP (Model Context Protocol) server designed for deployment on **AWS Bedrock AgentCore Runtime**.

## 📋 Changelog

### [1.1.0] - 2026-02-19

#### Added
- **Math utility tools**: `math_add`, `math_subtract`, `math_multiply`, `math_divide` — for testing AgentCore runtime connectivity without a database
- **AWS Secrets Manager integration**: Automatically fetches `DATABASE_URL` and `MCP_API_KEY` from secret `postgres-mcp/credentials` when running in AWS (`AWS_REGION` is set)
- **IAM authentication bypass**: `APIKeyMiddleware` skips `X-API-Key` validation when running inside AgentCore (IAM/SigV4 handles auth at the platform level)
- **`mcp-proxy-for-aws` IDE integration**: Connect Windsurf/Cursor directly to the deployed AgentCore runtime via SigV4-signed local proxy (no `X-API-Key` needed from IDE)
- **`boto3` dependency**: Added to `requirements.txt` for AWS Secrets Manager access
- **Deployment guide**: Comprehensive `docs/DEPLOYMENT_GUIDE.md` covering CLI, CloudFormation, and manual Docker deployment options with Mermaid architecture diagrams
- **Direct Code Deploy support**: `agentcore deploy` packages and deploys code directly — no Docker build required for AgentCore deployment

#### Changed
- Server now uses `mcp.streamable_http_app()` wrapped with `APIKeyMiddleware` ASGI middleware (previously relied on FastMCP's built-in runner)
- `get_secrets_from_aws()` is called at startup; environment variables serve as fallback for local development
- Resource URI pattern simplified to `postgres://schema/{table_name}` (FastMCP template format)

---

## Features

- **Read-Only Access**: All queries run within `READ ONLY` transactions
- **Streamable HTTP Transport**: Compatible with AWS AgentCore Runtime
- **Stateless Operation**: Supports horizontal scaling with session isolation
- **Database Schema Discovery**: List tables and describe column structures
- **Health Check Endpoint**: Container-ready with `/health` endpoint
- **API Key Authentication**: Secure access with `X-API-Key` header or Bearer token (auto-disabled in AWS)
- **AWS Secrets Manager**: Automatic credential fetching when deployed to AgentCore
- **Math Utility Tools**: Built-in arithmetic tools for connectivity testing

## Tools

| Tool | Description | Annotations |
|------|-------------|-------------|
| `postgres_query` | Run a read-only SQL SELECT query | `readOnlyHint: true`, `idempotentHint: true` |
| `math_add` | Add two numbers (a + b) | `readOnlyHint: true`, `idempotentHint: true` |
| `math_subtract` | Subtract two numbers (a - b) | `readOnlyHint: true`, `idempotentHint: true` |
| `math_multiply` | Multiply two numbers (a * b) | `readOnlyHint: true`, `idempotentHint: true` |
| `math_divide` | Divide two numbers (a / b), handles division by zero | `readOnlyHint: true`, `idempotentHint: true` |

## Resources

Resources are dynamically generated based on your database tables.

| Resource URI Pattern | Description |
|---------------------|-------------|
| `postgres://schema/{table_name}` | Get column definitions for a table |

When you call `list_resources()`, the server returns all tables in the `public` schema with URIs like:
- `postgres://schema/users`
- `postgres://schema/orders`

## Prerequisites

- Python 3.10+
- PostgreSQL database
- Docker (for containerized deployment)

## Installation

```bash
# Clone or navigate to the project
cd postgres-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Set the required environment variables:

```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
export MCP_API_KEY="your-secure-api-key"  # Optional but recommended
```

Or create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
# Edit .env with your database credentials and API key
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `MCP_API_KEY` | No | API key for authentication (recommended for production) |
| `AWS_REGION` | No (AWS only) | Set automatically by AgentCore; triggers Secrets Manager lookup and disables `X-API-Key` middleware |

> **AWS Secrets Manager**: When `AWS_REGION` is set and `DATABASE_URL` is absent, the server automatically fetches credentials from the secret named `postgres-mcp/credentials` (keys: `DATABASE_URL`, `MCP_API_KEY`).

## Local Development

### Start the MCP Server

```bash
python mcp_server.py
```

The server will start on `http://0.0.0.0:8000/mcp`

### Test with MCP Client

In a separate terminal:

```bash
python mcp_client.py
```

### Health Check

```bash
curl http://localhost:8000/health
```

### Test with API Key

```bash
# With X-API-Key header
curl -H "X-API-Key: your-api-key" http://localhost:8000/mcp

# With Authorization Bearer
curl -H "Authorization: Bearer your-api-key" http://localhost:8000/mcp
```

## Docker Deployment

### Build the Image

```bash
docker build -t postgres-mcp .
```

### Run the Container

```bash
docker run -d \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:password@host:port/database" \
  -e MCP_API_KEY="your-secure-api-key" \
  --name postgres-mcp \
  postgres-mcp
```

## AWS Bedrock AgentCore Deployment

This server is designed for deployment on AWS Bedrock AgentCore Runtime.

### Project Structure

```
postgres-mcp/
├── mcp_server.py          # Main MCP server (FastMCP + ASGI middleware)
├── mcp_client.py          # Local testing client
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container configuration
├── .env.example           # Environment template
├── docs/
│   └── DEPLOYMENT_GUIDE.md  # Full AgentCore deployment guide
└── README.md              # This file
```

> See [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) for comprehensive deployment instructions including CLI, CloudFormation, and manual Docker options.

### Deploy to AgentCore (Recommended: CLI)

1. **Install AgentCore Toolkit**:
   ```bash
   pip install bedrock-agentcore-starter-toolkit
   ```

2. **Configure**:
   ```bash
   export AWS_SHARED_CREDENTIALS_FILE=$(pwd)/.aws/credentials
   export AWS_PROFILE=<your-aws-profile>

   agentcore configure -e mcp_server.py \
     --protocol MCP \
     --disable-memory \
     --name postgres_mcp \
     --non-interactive \
     --region us-west-2
   ```

3. **Deploy** (Direct Code Deploy — no Docker required):
   ```bash
   agentcore deploy
   ```

4. **Verify**:
   ```bash
   agentcore status
   # Agent ARN: arn:aws:bedrock-agentcore:us-west-2:<account>:runtime/postgres_mcp-<id>
   ```

5. **Test**:
   ```bash
   agentcore invoke '{"jsonrpc":"2.0","method":"tools/list","id":1}'
   agentcore invoke '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"math_add","arguments":{"a":10,"b":5}},"id":2}'
   ```

> **Important**: Use underscores in agent name (`postgres_mcp`), not hyphens. See [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) for CloudFormation and manual Docker options.

### Key Configuration for AgentCore

The server uses these settings for AgentCore compatibility:

```python
mcp = FastMCP(
    name="postgres-mcp",
    host="0.0.0.0",
    port=8000,
    stateless_http=True,  # Required for AgentCore
)

# Wrap with API key middleware and serve via uvicorn
app = mcp.streamable_http_app()
app = APIKeyMiddleware(app)
uvicorn.run(app, host="0.0.0.0", port=8000)
```

- `stateless_http=True` — required for AgentCore's stateless request model
- `APIKeyMiddleware` — automatically bypassed when `AWS_REGION` is set (AgentCore handles auth via IAM)
- `streamable_http_app()` — exposes the MCP server at `/mcp` with streaming HTTP transport

## Security Considerations

- **API Key Authentication**: All endpoints (except `/health`) require valid API key when running locally
- **IAM / SigV4 (AgentCore)**: When deployed to AgentCore, `X-API-Key` middleware is automatically disabled — AWS IAM handles authentication at the platform level
- **AWS Secrets Manager**: Credentials are fetched at startup from `postgres-mcp/credentials`; never hardcoded
- **Read-Only**: All queries execute within `BEGIN TRANSACTION READ ONLY` and are always rolled back
- **Connection Pooling**: Uses `asyncpg` connection pool (min 1, max 10 connections, 60s timeout)
- **No DDL/DML**: Only SELECT and read operations are permitted

### Authentication

| Context | Method |
|---------|--------|
| Local development | `X-API-Key` header or `Authorization: Bearer <key>` |
| AgentCore (deployed) | IAM SigV4 via `mcp-proxy-for-aws` — no `X-API-Key` needed |
| `/health` endpoint | Always exempt (for container orchestration) |

## Example Usage

### postgres_query Tool

```json
{
  "name": "postgres_query",
  "arguments": {
    "sql": "SELECT * FROM users LIMIT 10"
  }
}
```

### Windsurf / IDE MCP Configuration

#### Local Server

Add to your `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "postgresql-local": {
      "serverUrl": "http://localhost:8000/mcp",
      "headers": {
        "X-API-Key": "your-api-key"
      }
    }
  }
}
```

#### AWS Bedrock AgentCore (Deployed)

Use [`mcp-proxy-for-aws`](https://pypi.org/project/mcp-proxy-for-aws/) to connect directly to the AgentCore runtime with SigV4 authentication — no `X-API-Key` required:

```json
{
  "mcpServers": {
    "agentcore-postgres-mcp": {
      "command": "uvx",
      "args": [
        "mcp-proxy-for-aws@latest",
        "https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/<url-encoded-agent-arn>/invocations?qualifier=DEFAULT"
      ],
      "env": {
        "AWS_PROFILE": "<your-aws-profile>",
        "AWS_REGION": "us-west-2",
        "AWS_SHARED_CREDENTIALS_FILE": "/path/to/postgres-mcp/.aws/credentials"
      }
    }
  }
}
```

> The Agent ARN in the URL must be URL-encoded (replace `:` with `%3A`, `/` with `%2F`). Requires `uv` installed (`brew install uv`).

All 5 tools will appear in the IDE after reloading MCP servers: `postgres_query`, `math_add`, `math_subtract`, `math_multiply`, `math_divide`.

## Troubleshooting

### Connection Issues

1. Verify `DATABASE_URL` is set correctly
2. Check database is accessible from the server
3. Ensure PostgreSQL allows connections from the server IP

### Health Check Failing

1. Check database connectivity
2. Review server logs for errors
3. Verify port 8000 is not blocked

## License

MIT License
