FROM python:3.12-slim
WORKDIR /opt/app
RUN pip install --no-cache-dir kafka-python-ng==2.2.3
COPY src /opt/app/src
ENV PYTHONPATH=/opt/app/src
ENTRYPOINT ["python", "-m", "amazon_review_intelligence.streaming.kafka_producer"]

