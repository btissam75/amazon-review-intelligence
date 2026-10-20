FROM spark:4.2.0-python3
USER root
RUN pip install --no-cache-dir scikit-learn==1.5.2 joblib==1.4.2 pymongo==4.10.1
RUN mkdir -p /home/spark/.ivy2.5.2 && chown -R spark:spark /home/spark
WORKDIR /opt/app
COPY src /opt/app/src
ENV PYTHONPATH=/opt/app/src
ENV HOME=/home/spark
USER spark

