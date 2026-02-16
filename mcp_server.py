"""
PostgreSQL MCP Server - Read-Only Database Access

A FastMCP-based MCP server that provides read-only access to PostgreSQL databases.
Designed for deployment on AWS Bedrock AgentCore Runtime.

This implementation matches the original TypeScript version:
https://github.com/modelcontextprotocol/servers-archived/blob/main/src/postgres/index.ts

Features:
- List database table schemas as resources (dynamically generated URIs)
- Read table column information
- Execute read-only SQL queries
"""

import json
import os
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import asyncpg
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import FunctionResource
from mcp.types import Resource

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Database configuration from environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "")

# API Key configuration for security
API_KEY = os.getenv("MCP_API_KEY", "")

# Schema path constant (matches original TypeScript)
SCHEMA_PATH = "schema"


def get_resource_base_url() -> str:
    """
    Generate the resource base URL from DATABASE_URL.
    Matches original TypeScript: postgres://user@host:port/database
    Password is removed for security.
    """
    if not DATABASE_URL:
        return "postgres://localhost/database"
    
    parsed = urlparse(DATABASE_URL)
    # Remove password, keep user, change scheme to postgres
    netloc = parsed.hostname or "localhost"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    if parsed.username:
        netloc = f"{parsed.username}@{netloc}"
    
    return urlunparse(("postgres", netloc, parsed.path, "", "", ""))


# Initialize FastMCP with stateless_http for AgentCore compatibility
mcp = FastMCP(
    name="postgres-mcp",
    host="0.0.0.0",
    port=8000,
    stateless_http=True,
)


# Connection pool (initialized lazily)
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Get or create the database connection pool."""
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Format: postgresql://user:password@host:port/database"
            )
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60,
        )
        logger.info("Database connection pool created successfully")
    return _pool


@asynccontextmanager
async def get_connection():
    """Context manager for database connections with automatic cleanup."""
    pool = await get_pool()
    conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn)


# =============================================================================
# MCP Resources - Database Schema Information
# Matches original TypeScript: ListResourcesRequestSchema, ReadResourceRequestSchema
# =============================================================================

async def get_table_schema(table_name: str) -> str:
    """
    Get the schema (columns and data types) for a specific table.
    
    Matches original TypeScript ReadResourceRequestSchema handler.
    
    Args:
        table_name: Name of the table to get schema for
        
    Returns:
        JSON representation of the table's column definitions
    """
    async with get_connection() as conn:
        # Matches original: SELECT column_name, data_type FROM information_schema.columns WHERE table_name = $1
        rows = await conn.fetch(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = $1",
            table_name
        )
        
        if not rows:
            return json.dumps({"error": f"Table '{table_name}' not found or has no columns"})
        
        columns = [
            {
                "column_name": row["column_name"],
                "data_type": row["data_type"],
            }
            for row in rows
        ]
        
        return json.dumps(columns, indent=2)


@mcp.resource("postgres://schema/{table_name}")
async def table_schema_resource(table_name: str) -> str:
    """
    Resource endpoint for table schema.
    URI format: postgres://schema/table_name
    """
    return await get_table_schema(table_name)


# =============================================================================
# MCP Tools - Read-Only Query Execution
# Matches original TypeScript: ListToolsRequestSchema, CallToolRequestSchema
# =============================================================================

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def postgres_query(sql: str) -> str:
    """
    Run a read-only SQL query against the PostgreSQL database.
    
    This tool executes SELECT queries in a read-only transaction.
    All queries are automatically rolled back after execution.
    
    Args:
        sql: The SQL SELECT query to execute. Example: "SELECT * FROM users LIMIT 10"
        
    Returns:
        JSON array of query results. Each row is a JSON object with column names as keys.
        
    Errors:
        - If the query is invalid, returns the PostgreSQL error message
        - If the table doesn't exist, suggests checking available tables with: 
          SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'
    """
    async with get_connection() as conn:
        try:
            # Matches original: BEGIN TRANSACTION READ ONLY
            await conn.execute("BEGIN TRANSACTION READ ONLY")
            
            try:
                rows = await conn.fetch(sql)
                results = [dict(row) for row in rows]
                return json.dumps(results, indent=2, default=str)
                
            finally:
                # Matches original: always ROLLBACK
                try:
                    await conn.execute("ROLLBACK")
                except Exception as e:
                    logger.warning(f"Could not roll back transaction: {e}")
                
        except asyncpg.PostgresError as e:
            logger.error(f"Database error executing query: {e}")
            raise Exception(str(e))


# =============================================================================
# Health Check Endpoint (for container orchestration)
# =============================================================================

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for container orchestration."""
    from starlette.responses import JSONResponse
    
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return JSONResponse({"status": "healthy", "database": "connected"})
    except Exception as e:
        return JSONResponse(
            {"status": "unhealthy", "error": str(e)},
            status_code=503
        )


# =============================================================================
# Main Entry Point
# =============================================================================

# =============================================================================
# API Key Authentication Middleware (ASGI)
# =============================================================================


class APIKeyMiddleware:
    """ASGI Middleware to validate API key in request headers."""
    
    EXEMPT_PATHS = {"/health"}
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        path = scope.get("path", "")
        
        # Skip authentication for exempt paths
        if path in self.EXEMPT_PATHS:
            return await self.app(scope, receive, send)
        
        # Skip if no API key is configured
        if not API_KEY:
            return await self.app(scope, receive, send)
        
        # Extract headers
        headers = dict(scope.get("headers", []))
        api_key_header = headers.get(b"x-api-key", b"").decode()
        auth_header = headers.get(b"authorization", b"").decode()
        
        provided_key = api_key_header or auth_header.replace("Bearer ", "")
        
        if not provided_key:
            await self._send_error(send, 401, "Missing API key. Provide X-API-Key header or Authorization: Bearer <key>")
            return
        
        if provided_key != API_KEY:
            await self._send_error(send, 403, "Invalid API key")
            return
        
        return await self.app(scope, receive, send)
    
    async def _send_error(self, send, status_code, message):
        """Send JSON error response."""
        import json as _json
        body = _json.dumps({"error": message}).encode()
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })


if __name__ == "__main__":
    logger.info("Starting PostgreSQL MCP Server...")
    logger.info(f"Database URL configured: {'Yes' if DATABASE_URL else 'No'}")
    logger.info(f"API Key configured: {'Yes' if API_KEY else 'No (authentication disabled)'}")
    
    import uvicorn
    
    # Get the ASGI app from FastMCP and wrap with middleware
    app = mcp.streamable_http_app()
    app = APIKeyMiddleware(app)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
