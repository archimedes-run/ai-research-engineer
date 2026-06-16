FROM python:3.12-slim

WORKDIR /app

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock* ./

# Install production dependencies into .venv
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ ./src/

# Create runtime data directory
RUN mkdir -p .data

ENV PYTHONPATH=/app/src
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "ai_research_engineer.server.app:app", \
     "--host", "0.0.0.0", "--port", "8001"]
