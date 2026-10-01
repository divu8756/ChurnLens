# syntax=docker/dockerfile:1
# ---- build: install the Python dependencies into a virtualenv ----
FROM python:3.14-slim AS build
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /build
# Dependencies only (from pyproject.toml), so a code change does not reinstall them:
# this layer is rebuilt only when pyproject.toml changes.
COPY pyproject.toml ./
RUN pip install --upgrade pip && python -c "import tomllib; \
print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" \
    > requirements.txt && pip install -r requirements.txt

# ---- runtime: slim, non-root, one process ----
# Memory (free hosts have 512 MB): few malloc arenas, one OpenMP thread (hosts report
# many CPUs), and pyarrow on the system allocator so freed memory is returned.
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    MALLOC_ARENA_MAX=2 \
    OMP_NUM_THREADS=1 \
    ARROW_DEFAULT_MEMORY_POOL=system

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
