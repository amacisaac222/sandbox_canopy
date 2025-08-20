#!/bin/bash
#
# CanopyIQ Database Migration Script
# Runs Alembic migrations to upgrade database to latest schema
#

set -e  # Exit on any error

echo "Starting CanopyIQ database migration..."

# Check if CP_DB_URL is set
if [ -z "$CP_DB_URL" ]; then
    echo "Warning: CP_DB_URL not set, using default SQLite database"
    export CP_DB_URL="sqlite+aiosqlite:///./canopyiq.db"
fi

echo "Database URL: $CP_DB_URL"

# Check if alembic is available
if ! command -v alembic &> /dev/null && ! python -m alembic --help &> /dev/null; then
    echo "Error: Alembic not found. Please install dependencies:"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Run migrations
echo "Running Alembic migrations..."
python -m alembic upgrade head

if [ $? -eq 0 ]; then
    echo "✅ Database migration completed successfully!"
else
    echo "❌ Database migration failed!"
    exit 1
fi

echo "Database schema is now up to date."