# tracer-gov-service — Government Audit Bridge for Liferay
# Base: Python 3.12-slim. Consumes winnex-tracer + winnex-ai-normalize +
# winnex-madhava 1.9.2 from PyPI.
FROM python:3.12-slim

WORKDIR /app

COPY tracer-gov-service/src/ /app/src/
COPY tracer-gov-service/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --force-reinstall -r /app/requirements.txt
RUN pip install --no-cache-dir --force-reinstall "winnex-madhava==1.9.2"

ENV PYTHONPATH=/app/src
EXPOSE 8601

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8601"]
