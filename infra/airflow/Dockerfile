# Custom Airflow 3 image: simulation CLI + dbt for daily_fintech_analytics DAG.
# Build context: repo root (see infra/docker-compose.yml).
FROM apache/airflow:3.1.5

USER airflow
COPY infra/airflow/requirements-airflow.txt /requirements-airflow.txt
RUN pip install --no-cache-dir -r /requirements-airflow.txt
