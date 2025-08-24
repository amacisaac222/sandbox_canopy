FROM python:3.12-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install minimal dependencies first
RUN pip install --no-cache-dir fastapi uvicorn[standard]

# Copy the entire project
COPY . .

# Set working directory to canopyiq_site for the app
WORKDIR /app/canopyiq_site

# Default port (Railway will override with $PORT)
ENV PORT=8000

# Use simple app first to test, then switch to full app
CMD sh -c "python -m uvicorn simple_app:simple_app --host 0.0.0.0 --port $PORT"