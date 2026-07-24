# ── Pinned versions (see VERSIONS.md) ───────────────────────────────────────
ARG GO_VERSION=1.26.4
ARG SUBFINDER_VERSION=v2.14.0
ARG DNSX_VERSION=v1.2.3
ARG HTTPX_VERSION=v1.9.0
ARG NUCLEI_VERSION=v3.9.0
ARG ALTERX_VERSION=v0.1.0

# Stage 1: Build ProjectDiscovery tools
FROM golang:${GO_VERSION}-bookworm AS builder

ARG SUBFINDER_VERSION
ARG DNSX_VERSION
ARG HTTPX_VERSION
ARG NUCLEI_VERSION
ARG ALTERX_VERSION

RUN go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@${SUBFINDER_VERSION} && \
    go install github.com/projectdiscovery/dnsx/cmd/dnsx@${DNSX_VERSION} && \
    go install github.com/projectdiscovery/httpx/cmd/httpx@${HTTPX_VERSION} && \
    go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@${NUCLEI_VERSION} && \
    go install github.com/projectdiscovery/alterx/cmd/alterx@${ALTERX_VERSION}

# Stage 2: Python runtime
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install runtime dependencies and scanner binaries
RUN apt-get update && apt-get install -y \
    nmap curl ca-certificates bash \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /go/bin/subfinder /usr/local/bin/
COPY --from=builder /go/bin/dnsx      /usr/local/bin/
COPY --from=builder /go/bin/httpx     /usr/local/bin/httpx-pd
COPY --from=builder /go/bin/nuclei    /usr/local/bin/
COPY --from=builder /go/bin/alterx    /usr/local/bin/

# Pre-download nuclei templates (templates float intentionally — see VERSIONS.md)
RUN nuclei -update-templates -silent || true

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py auth.py notify.py db.py ingest.py scanqueue.py scanner.py config.py containerlogs.py logroutes.py ./
COPY pipeline/ ./pipeline/
COPY alembic.ini ./
COPY alembic/ ./alembic/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
