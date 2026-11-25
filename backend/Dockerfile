# SmartPark — backend Flask sobre Ubuntu 24.04 LTS
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    TZ=America/Bogota \
    FLASK_APP=wsgi

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates tzdata curl \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/venv

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .
# Quita finales de línea de Windows (CRLF) por si el repo se clonó en Windows
RUN sed -i 's/\r$//' docker/entrypoint.sh \
 && chmod +x docker/entrypoint.sh \
 && useradd --create-home --uid 10001 smartpark \
 && chown -R smartpark /app
USER smartpark

EXPOSE 5000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
  CMD curl -fsS http://localhost:5000/api/salud || exit 1
ENTRYPOINT ["/app/docker/entrypoint.sh"]
