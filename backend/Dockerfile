FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m smartpark && chown -R smartpark /app
USER smartpark

EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:5000/api/salud')"
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:5000", "--access-logfile", "-", "wsgi:app"]
