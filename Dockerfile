# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -yq --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    default-mysql-client \
    pkg-config \
    curl \
    ca-certificates \
    gnupg \
    python3-dev \
    git \
    libgl1 \
    libsm6 \
    libxrender1 \
    libxext6 \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* ./
RUN npm install

COPY requirements.txt ./
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements.txt

COPY . ./
RUN npm run build-css

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -yq --no-install-recommends \
    default-libmysqlclient-dev \
    default-mysql-client \
    libgl1 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser \
    && useradd -r -u 1000 -g appuser appuser

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/local/include /usr/local/include
COPY --from=builder --chown=appuser:appuser /app /app
USER appuser
WORKDIR /app/algovision

EXPOSE 8000
CMD ["gunicorn", "algovision.wsgi:application", "--bind", "0.0.0.0:8000"]
