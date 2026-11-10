# Development tools only. Board-specific toolchains and mission dependencies
# are added after hardware/repository inspection.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       cmake \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# .dockerignore excludes prompts, credentials, Git internals and generated data.
# This is a snapshot: rebuild after editing host files.
COPY . /workspace

CMD ["sleep", "infinity"]
