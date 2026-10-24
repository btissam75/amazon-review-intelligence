FROM python:3.12-slim

WORKDIR /opt/app
COPY pyproject.toml README.md /opt/app/
COPY src /opt/app/src
RUN pip install --no-cache-dir ".[api]"

ENV PYTHONPATH=/opt/app/src
EXPOSE 8000
CMD ["uvicorn", "amazon_review_intelligence.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
