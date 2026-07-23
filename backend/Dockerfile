FROM python:3.12-slim

WORKDIR /app

# Node.js is required for Next.js live previews (npm install + next dev).
# Install from the official binary tarball so PATH is system-wide for the app user.
ARG NODE_VERSION=22.14.0
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
    && curl -fsSLo /tmp/node.tar.xz \
        "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm /tmp/node.tar.xz \
    && node --version \
    && npm --version \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --home /app --ingroup app app

COPY pyproject.toml .
COPY app/ app/

# Editable install so runtime imports /app/app (not a stale site-packages copy).
# Hotfixes and rebuilds stay in sync with the files in the image WORKDIR.
RUN pip install --no-cache-dir --no-compile --root-user-action=ignore -e . \
    && find /usr/local/lib/python3.12 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
    mkdir -p /app/projects /app/data /app/.local/share /app/.npm \
    && chown -R app:app /app

ENV HOME=/app
ENV XDG_DATA_HOME=/tmp/app-data
ENV TMPDIR=/tmp/app-data
ENV PYTHONPATH=/app
ENV npm_config_cache=/app/.npm
# `su app` can strip PATH — keep node/npm discoverable for previews.
ENV PATH=/usr/local/bin:/usr/bin:/bin
# Bind Next previews on all interfaces so published Docker ports work.
ENV RUNTIME_BIND_HOST=0.0.0.0
ENV RUNTIME_PUBLIC_HOST=127.0.0.1
ENV RUNTIME_PORT_BASE=3100
ENV RUNTIME_PORT_SPAN=50

# API + Next.js preview port range (must match docker-compose publish)
EXPOSE 8000
EXPOSE 3100-3149

CMD ["sh", "-c", "mkdir -p /app/projects /app/data /tmp/app-data /app/.npm && chown -R app:app /app/projects /app/data /tmp/app-data /app/.npm && su app -s /bin/sh -c 'export PATH=/usr/local/bin:/usr/bin:/bin; exec uvicorn app.main:app --host 0.0.0.0 --port 8000'"]