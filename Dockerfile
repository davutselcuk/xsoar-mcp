FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

ENV XSOAR_URL="" \
    XSOAR_API_KEY="" \
    XSOAR_VERIFY_SSL="true"

CMD ["xsoar-mcp"]
