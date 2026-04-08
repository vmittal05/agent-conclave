FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install the project into /app
COPY . /app
WORKDIR /app

# Allow statements and log messages to immediately appear in the logs
ENV PYTHONUNBUFFERED=1

# Prepare virtual environment path
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv sync --active

# Set host and port
ENV HOST 0.0.0.0
EXPOSE 8080

# Run ADK API Server (Standard mode for Orchestrator)
CMD ["python3", "adk_app.py", "--host", "0.0.0.0", "--port", "8080", "--trace_to_cloud"]
