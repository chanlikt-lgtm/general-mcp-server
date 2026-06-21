# MCP Server — Dockerfile
# Works on: Render, Railway, Fly.io, Docker Desktop, any container host

FROM python:3.11-slim

# ffmpeg for audio/video tools (comment out to save ~80 MB if not needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (cached layer — only re-runs when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Ensure data directory exists
RUN mkdir -p data

# Port — Render/Railway/Fly set $PORT; default 8080 for local Docker
EXPOSE 8080

# Health check for container orchestrators
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Entry point — uses $PORT if set, else 8080
CMD uvicorn cloud_server:app --host 0.0.0.0 --port ${PORT:-8080}

