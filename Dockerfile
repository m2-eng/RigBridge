# ──────────────────────────────────────────────────────────────────────────────
# Dockerfile – RigBridge
# Multi-Stage-Build: builder installiert Abhaengigkeiten,
# runtime enthaelt nur das fuer den Betrieb Notwendige.
# ──────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Abhaengigkeiten zuerst kopieren (Layer-Caching nutzen)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Installierte Pakete aus dem builder-Stage uebernehmen
COPY --from=builder /install /usr/local

# Quellcode kopieren
COPY src/ ./src/
COPY protocols/ ./protocols/

# Kein Root im Container
RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

# Port fuer die Web-API (wird in docker-compose.yml gemappt)
EXPOSE 8080

# Startbefehl – wird spaeter auf den echten Einstiegspunkt gesetzt
CMD ["python", "-m", "src.backend.api"]
