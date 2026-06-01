FROM python:3.11-slim

WORKDIR /app

# Install build dependencies for ChromaDB and SQLite
RUN apt-get update && apt-get install -y \
    build-essential \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

# Install uv and dependencies
RUN pip install uv
RUN uv pip install --system "google-genai" "fastapi" "uvicorn[standard]" "loguru" "websockets" "pydantic-settings" "chromadb" "sentence-transformers" "sqlalchemy"

COPY . .

# Expose port
EXPOSE 8420

# Run the application
CMD ["python", "-m", "maxis.main"]
