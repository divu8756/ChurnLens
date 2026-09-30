# syntax=docker/dockerfile:1
# ---- build: install the Python dependencies into a virtualenv ----
FROM python:3.14-slim AS build
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
# Install the project to resolve its pinned dependencies, then drop the project itself:
# the runtime image runs the code from /app so paths like sample_data resolve there.
RUN pip install --upgrade pip && pip install . && pip uninstall -y churnlens-backend

# ---- runtime: slim, non-root, one process ----
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib

# OpenMP runtime used by scikit-learn.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY app ./app
COPY sample_data ./sample_data
RUN mkdir -p /app/data && chown -R app:app /app
USER app

ENV DATA_DIR=/app/data PORT=8000
EXPOSE 8000
# One worker: the SSE progress stream and the background analysis threads live in this
# process. --proxy-headers takes the client IP from the platform proxy (Render), which the
# per-IP rate limits need.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
