FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CCL_PROJECT_ROOT=/app/projects \
    CCL_BACKUP_ROOT=/app/backups

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

# Keep application-managed filesystem roots private.  The corresponding
# Compose volumes are mounted after this layer and inherit these permissions
# when they are first created.
RUN install -d -m 0750 /app/projects /app/backups

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn main:app --host 0.0.0.0 --port 8000"]
