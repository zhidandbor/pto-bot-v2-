FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /opt/app/requirements.txt
RUN pip install --upgrade pip && pip install -r /opt/app/requirements.txt

COPY alembic.ini /opt/app/alembic.ini
COPY alembic /opt/app/alembic
COPY app /opt/app/app

ENV PYTHONPATH=/opt/app

CMD ["python", "-m", "app.main"]