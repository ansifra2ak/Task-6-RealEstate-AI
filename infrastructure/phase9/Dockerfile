FROM node:22-bookworm-slim AS frontend
WORKDIR /src
COPY frontend/phase6/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
COPY frontend/phase6/ ./
RUN npm test && npm run build
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MLFLOW_ENABLE_TELEMETRY=false OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements*.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements-phase7.txt -c constraints.txt
COPY backend ./backend
COPY ml-pipeline/registry ./ml-pipeline/registry
COPY --from=frontend /src/dist ./frontend/phase6/dist
RUN useradd --uid 10001 --create-home task6 && mkdir -p data reports visualizations champion && chown -R task6:task6 /app
USER 10001:10001
CMD ["python", "-m", "backend.phase9_runtime", "api"]
