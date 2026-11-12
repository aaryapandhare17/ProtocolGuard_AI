# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontends
WORKDIR /build
COPY package.json package-lock.json ./
COPY apps/admin/package.json apps/admin/package.json
COPY apps/securebank/package.json apps/securebank/package.json
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci
COPY apps ./apps
RUN ADMIN_BASE_PATH=/admin/ npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PROTOCOLGUARD_ENV=production STATIC_DIRECTORY=/app/web \
    DATABASE_URL=sqlite:////var/data/protocolguard.db \
    ML_MODEL_DIRECTORY=/app/ml/artifacts/bank-v2 \
    ML_COMPARISON_REPORT=/app/ml/evaluation/comparison-v2.json \
    SIMULATION_ENABLED=false
WORKDIR /app
COPY backend ./backend
COPY --from=frontends /build/apps/securebank/dist ./web/bank
COPY --from=frontends /build/apps/admin/dist ./web/admin
# Train trusted artifacts in the same environment that loads them. No local binary
# artifacts or passwords enter the build context. The data is removed in this layer.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    python -m pip install --no-cache-dir './backend[ml]' \
    && python -m app.ml.dataset --sessions 10000 --seed 42 --output ml/datasets/bank-v2 \
    && python -m app.ml.train --dataset ml/datasets/bank-v2 --output ml/artifacts/bank-v2 --seed 42 \
    && python -m app.ml.compare --dataset ml/datasets/bank-v2 --artifacts ml/artifacts/bank-v2 --output ml/evaluation/comparison-v2.json \
    && python -m app.ml.validate_live --artifacts ml/artifacts/bank-v2 --output ml/evaluation/login-coverage-v2.json \
    && rm -rf ml/datasets \
    && mkdir -p /var/data
EXPOSE 10000
CMD ["python", "-m", "app.deploy"]
