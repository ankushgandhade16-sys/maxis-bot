FROM python:3.11-slim

WORKDIR /app

# Install build dependencies for ChromaDB and SQLite
RUN apt-get update && apt-get install -y \
    build-essential \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

# Install dependencies with extended timeout for Render free-tier
RUN pip install --no-cache-dir --timeout=300 --retries=10 \
    "google-genai" "fastapi" "uvicorn[standard]" "loguru" "websockets" \
    "pydantic-settings" "sqlalchemy" "psycopg2-binary" "pinecone" \
    "edge-tts" "psutil" "mss" "Pillow" "httpx"

RUN pip install --no-cache-dir --timeout=300 --retries=10 \
    "chromadb" "sentence-transformers"


COPY . .

# Expose port
EXPOSE 8420

# Run the application
CMD ["python", "-m", "maxis.main"]
