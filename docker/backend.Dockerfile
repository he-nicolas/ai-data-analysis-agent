# Backend: FastAPI + LangGraph agents
FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock* ./

COPY src/ ./src/
RUN pip install --no-cache-dir -e . || pip install --no-cache-dir .

COPY data/example_db/ ./data/example_db/
COPY data/example_file/ ./data/example_file/

RUN mkdir -p /app/data/uploaded_files /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

CMD ["uvicorn", "ai_data_analysis_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]