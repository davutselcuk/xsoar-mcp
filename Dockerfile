FROM python:3.14-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip build && \
    python -m build --wheel

# ── runtime ────────────────────────────────────────────────────────────────
FROM python:3.14-slim

LABEL org.opencontainers.image.title="xsoar-mcp"
LABEL org.opencontainers.image.description="MCP server for Palo Alto Cortex XSOAR"
LABEL org.opencontainers.image.source="https://github.com/davutselcuk/xsoar-mcp"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Run as non-root
RUN useradd --create-home --shell /bin/bash xsoar
USER xsoar

ENV XSOAR_URL="" \
    XSOAR_API_KEY="" \
    XSOAR_VERIFY_SSL="true" \
    XSOAR_READ_ONLY="false" \
    XSOAR_DEBUG="false"

CMD ["xsoar-mcp"]
