FROM python:3.10-slim
WORKDIR /app
RUN pip install --no-cache-dir pymongo pandas numpy pyarrow
COPY ingestion/ /app/ingestion/
COPY storage/load_to_mongo.py /app/load_to_mongo.py
