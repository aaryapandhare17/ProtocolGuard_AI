# syntax=docker/dockerfile:1
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PROTOCOLGUARD_ENV=production SERVE_FRONTENDS=false \
    DATABASE_URL=sqlite:////var/data/protocolguard.db \
    ML_MODEL_DIRECTORY=/app/ml/artifacts/bank-v2 \
    ML_COMPARISON_REPORT=/app/ml/evaluation/comparison-v2.json \
    SIMULATION_ENABLED=false IP_AUTO_RESTRICT_ENABLED=false
WORKDIR /app
COPY backend ./backend
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    python -m pip install --no-cache-dir './backend[ml]' \
    && python -m app.ml.dataset --sessions 10000 --seed 42 --output ml/datasets/bank-v2 \
    && python -m app.ml.train --dataset ml/datasets/bank-v2 --output ml/artifacts/bank-v2 --seed 42 \
    && python -m app.ml.compare --dataset ml/datasets/bank-v2 --artifacts ml/artifacts/bank-v2 --output ml/evaluation/comparison-v2.json \
    && python -m app.ml.validate_live --artifacts ml/artifacts/bank-v2 --output ml/evaluation/login-coverage-v2.json \
    && rm -rf ml/datasets && mkdir -p /var/data
EXPOSE 10000
CMD ["python", "-m", "app.deploy"]
