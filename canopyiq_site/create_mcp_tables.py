"""
Database migration script to create MCP tables
Run this to add MCP monitoring tables to your existing database
"""
import asyncio
import logging
from database import Base, engine, DATABASE_URL
from mcp_models import MCPSession, MCPFileAccess, MCPProjectContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_mcp_tables():
    """Create MCP-specific tables in the database"""
    logger.info(f"Creating MCP tables in database: {DATABASE_URL}")
    
    if engine is None:
        logger.error("❌ Database engine not available")
        return
    
    try:
        async with engine.begin() as conn:
            # Create all MCP tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ MCP tables created successfully")
            
    except Exception as e:
        logger.error(f"❌ Failed to create MCP tables: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_mcp_tables())