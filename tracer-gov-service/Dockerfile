# tracer-gov-service - Government Audit Bridge for Liferay
# Base: Python 3.12-slim (cp312 wheel for winnex-madhava) + vendored tracer-gov.
FROM python:3.12-slim

WORKDIR /app

# Vendored tracer-gov sources (core engine + persistence + compliance).
COPY vendor/tracer-gov/ /app/tracer-gov/
COPY tracer-gov-service/src/ /app/src/
COPY tracer-gov-service/requirements.txt /app/requirements.txt

# winnex-madhava 1.8.8 depends only on numpy (cp312 wheel, no compiler).
RUN pip install --no-cache-dir -r /app/requirements.txt

ENV PYTHONPATH=/app/src:/app/tracer-gov
EXPOSE 8601

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8601"]
