# syntax=docker/dockerfile:1
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 AS builder
ARG DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -yq --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    ca-certificates \
    gnupg \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    git \
    libgl1 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update && apt-get install -yq --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* ./
RUN npm install

COPY requirements.txt .
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements.txt

COPY . .s

RUN npm run build-css

# Final stage
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04
ARG DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -yq --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    git \
    libgl1 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app

EXPOSE 8000

CMD ["gunicorn", "algovision.wsgi:application", "--bind", "0.0.0.0:8000"]
