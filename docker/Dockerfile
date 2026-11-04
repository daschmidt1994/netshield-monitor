# syntax=docker/dockerfile:1.7
# ---- Stage 1: build the web UI ------------------------------------------------
FROM node:20.19-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npx tsc --noEmit && npx vite build --outDir /web/dist

# ---- Stage 2: Python runtime ---------------------------------------------------
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/netshield ./netshield
COPY --from=web /web/dist ./netshield/static
RUN pip install --root-user-action=ignore ".[postgres]" \
 && rm -rf /root/.cache \
 && useradd --system --uid 10001 --home-dir /data --shell /usr/sbin/nologin netshield \
 && mkdir -p /data && chown netshield /data
USER netshield
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=4).status == 200 else 1)"
CMD ["netshield", "serve", "--host", "0.0.0.0", "--port", "8080"]
