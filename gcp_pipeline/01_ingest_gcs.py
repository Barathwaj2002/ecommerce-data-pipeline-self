from google.cloud import storage
import pandas as pd
import io
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger=logging.getLogger(__name__)

PROJECT_ID="ecommerce-pipeline-490613"
BUCKET_NAME="ecommerce-pipeline-example"
RAW_PATH="raw/online_retail.csv"
PROCESSED_PATH="processed/cleaned_data.parquet"

def validate_data(df, stage_name):
    logger.info("Validating data at stage: %s", stage_name)
    
    if len(df)==0:
        raise ValueError("Empty Dataframe at stage: %s", stage_name)
    logger.info("Row count: %d", len(df))

    required_columns = ['CustomerID', 'InvoiceDate', 'Quantity', 'UnitPrice', 'TotalPrice']
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError("Missing columns at %s : %s",stage_name, missing)
    logger.info("All required columns are present")

    null_counts = df[required_columns].isnull().sum()
    nulls_found = null_counts[null_counts>0]
    if len(nulls_found) > 0:
        logger.warning("Null value found: %s", nulls_found.to_dict())
    
    if(df['Quantity'] <= 0).any():
        raise ValueError("Negative or zero Quantity values found at %s", stage_name)
    if(df['UnitPrice'] <= 0).any():
        raise ValueError("Negative or zero UnitPrice values found at %s", stage_name)

    logger.info("Validation passed at stage: %s", stage_name)
    return True


def get_gcs_client():
    return storage.Client(project=PROJECT_ID)

def read_csv_from_gcs(client, bucket_name, blob_path):
    logger.info("Reading gcs://%s/%s", bucket_name, blob_path)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    data  = blob.download_as_bytes()
    df = pd.read_csv(io.BytesIO(data), encoding="unicode_escape")
    logger.info("Loaded %d rows, %d columns", len(df), len(df.columns))
    return df

def clean_data(df):
    logger.info("Cleaning data...")
    df = df.dropna(subset=['CustomerID', 'Description'])
    df = df[df['Quantity'] > 0]
    df = df[df['UnitPrice'] > 0]
    df['TotalPrice'] = df['Quantity'] * df['UnitPrice']
    df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'])
    logger.info("After cleaning: %d rows", len(df))
    return df

def write_parquet_to_gcs(client, df, bucket_name, blob_path):
    logger.info("Writing cleaned data to gcs://%s/%s", bucket_name, blob_path)
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, coerce_timestamps='us', allow_truncated_timestamps=True)
    buffer.seek(0)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_file(buffer, content_type = 'application/octet-stream')
    logger.info("Written %d rows to GCS", len(df))

if __name__ == "__main__":
    try:

        client = get_gcs_client()
        df = read_csv_from_gcs(client, BUCKET_NAME, RAW_PATH)
        df_clean = clean_data(df)
        validate_data(df_clean, "post-cleaning")
        write_parquet_to_gcs(client, df_clean, BUCKET_NAME, PROCESSED_PATH)
        logger.info("Ingestion Done")
    except Exception as e:
        logger.error("Ingestion failed: %s", e, exc_info=True)
        raise


