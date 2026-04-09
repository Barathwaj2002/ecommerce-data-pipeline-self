from google.cloud import bigquery
import os
import logging

PROJECT_ID = "ecommerce-pipeline-490613"
DATASET_ID = "ecommerce_data"
BUCKET = "ecommerce-pipeline-example"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger=logging.getLogger(__name__)

def get_bq_client():
    return bigquery.Client(project=PROJECT_ID)

def load_parquet_to_bq (client, gcs_uri, table_id, expected_min_rows=10):
    logger.info("Loading %s into %s", gcs_uri, table_id)

    job_config = bigquery.LoadJobConfig(
        source_format = bigquery.SourceFormat.PARQUET,
        write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True
    )

    load_job = client.load_table_from_uri(
        gcs_uri,
        table_id,
        job_config = job_config
    )

    load_job.result()

    table = client.get_table(table_id)
    actual_rows = table.num_rows

    logger.info("Loaded %d rows into %s", table.num_rows, table_id)

    if actual_rows == 0:
        raise ValueError(f"Zero rows loaded into {table_id}")
    if actual_rows <= expected_min_rows:
        logger.warning("Low row count in %s: %d (expected >= %d)", table_id, actual_rows, expected_min_rows)
    return actual_rows

if __name__=="__main__":
    try:
        client = get_bq_client()

        load_parquet_to_bq(
            client,
            gcs_uri=f"gs://{BUCKET}/processed/day4_ranked_products.parquet/*",
            table_id=f"{PROJECT_ID}.{DATASET_ID}.product_revenue"
        )

        load_parquet_to_bq(
            client,
            gcs_uri=f"gs://{BUCKET}/processed/customer_rfm.parquet/*",
            table_id = f"{PROJECT_ID}.{DATASET_ID}.customer_rfm"
        )
        logger.info("BigQuery load complete")
    except Exception as e:
        logger.error("BigQuery load error %s", e, exec_info=True)
        raise
