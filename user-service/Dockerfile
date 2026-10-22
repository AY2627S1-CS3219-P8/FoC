FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import ssl, urllib.request; context = ssl.create_default_context(cafile='/run/tls/ca.crt'); urllib.request.urlopen('https://localhost:8080/ready', context=context)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--ssl-certfile", "/run/tls/user-service.crt", "--ssl-keyfile", "/run/tls/user-service.key"]
