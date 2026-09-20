FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8765 \
    JOB_DATA_PATH=data/deploy/recruitment_jobs_deploy.csv.gz \
    RAG_CACHE_PATH=/tmp/rag_runtime_cache.pkl \
    RAG_MAX_FEATURES=8000

WORKDIR /app
COPY requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt
COPY . .

EXPOSE 8765
CMD ["sh", "-c", "gunicorn --chdir src --bind 0.0.0.0:${PORT:-8765} --workers 1 --threads 4 --timeout 180 agent.flask_server:app"]
