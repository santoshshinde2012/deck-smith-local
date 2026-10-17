# syntax=docker/dockerfile:1.7
# Two stages: dependencies resolved from uv.lock (reproducible), then a slim non-root runtime.
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --extra ui --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --extra ui --no-editable

FROM python:3.13-slim AS runtime
# The runtime runs from /opt/venv and never needs pip. The base image's pip bundles its own copies of
# msgpack, urllib3 and setuptools (pkg_resources), which trivy reports (e.g. GHSA-6v7p-g79w-8964,
# CVE-2025-47273); even the latest pip still bundles them, so pip is removed rather than upgraded.
RUN python -m pip uninstall --yes --no-cache-dir pip \
 && groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --home-dir /app app
ENV DECKSMITH_HOME=/app PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --chown=app:app configs ./configs
COPY --chown=app:app evals ./evals
COPY --chown=app:app src/decksmith/interfaces/ui.py ./ui.py
RUN mkdir -p /app/out /app/data && chown app:app /app/out /app/data
USER app
EXPOSE 8000 8501
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD ["python", "-c", "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
CMD ["uvicorn", "--factory", "decksmith.interfaces.api:app", "--host", "0.0.0.0", "--port", "8000"]
