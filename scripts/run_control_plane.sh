#!/bin/bash

# Agent Sandbox Control Plane Launcher
set -e

# Default environment
export CP_DB_URL="${CP_DB_URL:-sqlite+aiosqlite:///./sandbox.db}"
export CP_TENANT_SECRET="${CP_TENANT_SECRET:-devsecret_change_me}"
export CP_BIND="${CP_BIND:-0.0.0.0}"
export CP_PORT="${CP_PORT:-8080}"

echo "Starting Agent Sandbox Control Plane..."
echo "Database: $CP_DB_URL"
echo "Binding to: $CP_BIND:$CP_PORT"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Start the server
exec uvicorn control_plane.app:app --host "$CP_BIND" --port "$CP_PORT" --reload