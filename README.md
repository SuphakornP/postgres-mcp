# PostgreSQL MCP Server

A **FastMCP-based** read-only PostgreSQL MCP (Model Context Protocol) server designed for deployment on **AWS Bedrock AgentCore Runtime**.

## Features

- **Read-Only Access**: All queries run within `READ ONLY` transactions
- **Streamable HTTP Transport**: Compatible with AWS AgentCore Runtime
- **Stateless Operation**: Supports horizontal scaling with session isolation
- **Database Schema Discovery**: List tables and describe column structures
- **Health Check Endpoint**: Container-ready with `/health` endpoint
- **API Key Authentication**: Secure access with `X-API-Key` header or Bearer token

## Tools

| Tool | Description | Annotations |
|------|-------------|-------------|
| `postgres_query` | Run a read-only SQL query | `readOnlyHint: true`, `idempotentHint: true` |

## Resources

Resources are dynamically generated based on your database tables.

| Resource URI Pattern | Description |
|---------------------|-------------|
| `postgres://user@host:port/database/table_name/schema` | Get column definitions for a table |

When you call `list_resources()`, the server returns all tables in the `public` schema with URIs like:
- `postgres://user@host:5432/mydb/users/schema`
- `postgres://user@host:5432/mydb/orders/schema`

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
├── mcp_server.py          # Main MCP server
├── mcp_client.py          # Local testing client
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container configuration
├── .env.example           # Environment template
└── README.md              # This file
```

### Deploy to AgentCore

1. **Install AgentCore SDK**:
   ```bash
   pip install bedrock-agentcore-starter-toolkit
   ```

2. **Configure Deployment**:
   ```python
   from bedrock_agentcore_starter_toolkit import Runtime
   
   agentcore_runtime = Runtime()
   
   agentcore_runtime.configure(
       entrypoint="mcp_server.py",
       auto_create_execution_role=True,
       auto_create_ecr=True,
       requirements_file="requirements.txt",
       region="us-east-1",
       protocol="MCP",
       agent_name="postgres-mcp"
   )
   ```

3. **Launch**:
   ```python
   launch_result = agentcore_runtime.launch()
   print(f"Agent ARN: {launch_result.agent_arn}")
   ```

### Key Configuration for AgentCore

The server uses these settings for AgentCore compatibility:

```python
mcp = FastMCP(
    name="postgres-mcp",
    host="0.0.0.0",
    port=8000,
    stateless_http=True,  # Required for AgentCore
)

# Run with streamable-http transport
mcp.run(transport="streamable-http")
```

## Security Considerations

- **API Key Authentication**: All endpoints (except `/health`) require valid API key
- **Read-Only**: All queries execute within `BEGIN TRANSACTION READ ONLY`
- **Connection Pooling**: Uses `asyncpg` connection pool (1-10 connections)
- **Environment Variables**: Database credentials via environment, not hardcoded
- **No DDL/DML**: Only SELECT and read operations are permitted

### Authentication

Clients must provide the API key via one of:
- `X-API-Key` header: `X-API-Key: your-api-key`
- `Authorization` header: `Authorization: Bearer your-api-key`

The `/health` endpoint is exempt from authentication for container orchestration.

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

### Windsurf MCP Configuration

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
