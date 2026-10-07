FROM python:3.14-slim

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends file tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CCL_PROJECT_ROOT=/app/projects \
    CCL_BACKUP_ROOT=/app/backups

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

# Keep application-managed filesystem roots private.  The corresponding
# Compose volumes are initialized with the same owner on first use.  The
# storage-init service migrates existing volumes before the API starts.
RUN groupadd --system --gid 10001 ccl \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --home-dir /app ccl \
    && install -d -m 0750 -o 10001 -g 10001 /app/projects /app/backups

COPY scripts/prepare-storage.sh /usr/local/bin/prepare-storage.sh
RUN chmod 0755 /usr/local/bin/prepare-storage.sh

USER 10001:10001

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn main:app --host 0.0.0.0 --port 8000"]
