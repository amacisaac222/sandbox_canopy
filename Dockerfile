FROM python:3.12-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY canopyiq_site/requirements.txt .

# Install dependencies  
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Set working directory to canopyiq_site for the app
WORKDIR /app/canopyiq_site

# Default port (Railway will override with $PORT)
ENV PORT=8000

# Start with simple app that definitely works, then we can debug
CMD sh -c "python -m uvicorn simple_app:simple_app --host 0.0.0.0 --port $PORT"