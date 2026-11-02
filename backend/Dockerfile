FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FORECAST_LOG_PATH=/app/data/forecast/predictions.csv FORECAST_ACTUALS_PATH=/app/data/forecast/actuals.csv
WORKDIR /app
COPY requirements-ml.txt ./requirements-ml.txt
RUN pip install --no-cache-dir -r requirements-ml.txt
ARG INCLUDE_XGBOOST=false
RUN if [ "$INCLUDE_XGBOOST" = "true" ]; then pip install --no-cache-dir xgboost==2.1.4; fi
COPY app ./app
RUN groupadd --system voltgrid && useradd --system --uid 10001 --gid voltgrid --home-dir /app voltgrid \
    && mkdir -p /app/models/current /app/data/forecast /mlflow \
    && chown -R voltgrid:voltgrid /app /mlflow
USER voltgrid
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
