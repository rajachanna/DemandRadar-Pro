FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md /app/
COPY demandradar /app/demandradar
RUN pip install --no-cache-dir .
RUN useradd -m runner && mkdir -p /app/data && chown -R runner:runner /app/data
USER runner
EXPOSE 8090
CMD ["uvicorn", "demandradar.api:app", "--host", "0.0.0.0", "--port", "8090"]
