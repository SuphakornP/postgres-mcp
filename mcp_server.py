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

@mcp.tool()
async def query(sql: str) -> str:
    """
    Run a read-only SQL query.
    
    Matches original TypeScript implementation:
    - Wraps query in BEGIN TRANSACTION READ ONLY
    - Always ROLLBACKs after execution
    - Returns JSON-formatted results
    
    Args:
        sql: The SQL query to execute
        
    Returns:
        JSON-formatted query results
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

if __name__ == "__main__":
    logger.info("Starting PostgreSQL MCP Server...")
    logger.info(f"Database URL configured: {'Yes' if DATABASE_URL else 'No'}")
    mcp.run(transport="streamable-http")
