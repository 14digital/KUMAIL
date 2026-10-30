# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
# uv is installed with verified TLS; a cloud build can supply its CA bundle.
RUN --mount=type=secret,id=proxy_ca,target=/run/secrets/proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir uv==0.9.7
RUN --mount=type=secret,id=proxy_ca,target=/run/secrets/proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --frozen --no-dev
COPY --chown=10001:10001 backend backend
ENV PYTHONPATH=/app/backend PATH=/app/.venv/bin:$PATH STATE_DIR=/data
RUN useradd --uid 10001 --create-home app && mkdir /data && chown app /data
USER app
CMD ["uvicorn","intelligence.api:app","--host","0.0.0.0","--port","8000"]
