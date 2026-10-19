FROM spark:4.2.0-python3
USER root
RUN pip install --no-cache-dir scikit-learn==1.5.2 joblib==1.4.2 pymongo==4.10.1
WORKDIR /opt/app
COPY src /opt/app/src
ENV PYTHONPATH=/opt/app/src
USER spark

