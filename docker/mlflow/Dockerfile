# syntax=docker/dockerfile:1.7
FROM python:3.13-slim
RUN pip install --no-cache-dir "mlflow==3.17.1" "psycopg2-binary==2.9.10" "boto3==1.35.99" \
 && groupadd --system --gid 10001 mlflow && useradd --system --uid 10001 --gid mlflow --create-home mlflow \
 && mkdir -p /mlartifacts && chown mlflow:mlflow /mlartifacts
USER mlflow
EXPOSE 5000
HEALTHCHECK --interval=15s --timeout=3s --retries=10 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)"]
