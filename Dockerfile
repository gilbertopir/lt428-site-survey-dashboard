# ── Base image ────────────────────────────────────────────────
FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libgeos-dev \
    libproj-dev \
    proj-data \
    proj-bin \
    libsqlite3-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ───────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy project files ────────────────────────────────────────
COPY . .

# ── Create required directories ───────────────────────────────
RUN mkdir -p /app/data \
             /app/media/photos/features \
             /app/media/photos/passing_places \
             /app/media/map_cache \
             /app/staticfiles \
             /app/db

# ── Entrypoint ────────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
CMD ["/entrypoint.sh"]
