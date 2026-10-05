FROM ghcr.io/astral-sh/uv:0.8.15 AS uv

FROM python:3.12-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim
RUN groupadd --system mcp && useradd --system --gid mcp --home /var/lib/snipeit-copilot-mcp --shell /usr/sbin/nologin mcp \
    && install -d -o mcp -g mcp -m 0700 /var/lib/snipeit-copilot-mcp
WORKDIR /app
COPY --from=builder /build/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    FASTMCP_HOME=/var/lib/snipeit-copilot-mcp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER mcp:mcp
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
ENTRYPOINT ["python", "-m", "snipeit_copilot_mcp"]

