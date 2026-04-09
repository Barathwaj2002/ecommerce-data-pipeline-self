from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, sum as sum_, row_number, desc, round,
    count, coalesce, lit, to_timestamp
)
from pyspark.sql.window import Window
from pyspark.sql.functions import max as max_
import logging

BUCKET = "gs://ecommerce-pipeline-example"
INPUT_PATH = f"{BUCKET}/processed/cleaned_data.parquet"
OUTPUT_PATH_1 = f"{BUCKET}/processed/day4_ranked_products.parquet"
OUTPUT_PATH_2 = f"{BUCKET}/processed/customer_rfm.parquet"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger=logging.getLogger(__name__)

def validate_spark_df(df, stage_name, min_rows=100):
    count = df.count()
    logger.info("Row count at %s: %d", stage_name, count)

    if count == 0:
        raise ValueError("Empty dataframe at stage: %s", stage_name)
    
    if count < min_rows:
        logger.warning("Low row count at %s: %d (expected >= %d)", stage_name, min_rows)

    return count

def main():
    try:
        spark = SparkSession.builder \
            .appName("Day4_Advanced") \
            .config("spark.sql.parquet.int96RebaseModeInRead", "CORRECTED") \
            .config("spark.sql.parquet.int96RebaseModeInWrite", "CORRECTED") \
            .getOrCreate()

        df = spark.read.parquet(INPUT_PATH)
        validate_spark_df(df, "after_fetching_the_data", min_rows=100000)

        logger.info("Loaded %d rows and %d columns", df.count, len(df.columns))

        df = df.withColumn(
            "InvoiceDate",
            to_timestamp(col("InvoiceDate"))
        )

        df = df.withColumn("Quantity", col("Quantity").cast("int")) \
               .withColumn("UnitPrice", col("UnitPrice").cast("double"))

        df = df.withColumn("TotalPrice", col("Quantity") * col("UnitPrice"))

        rfm_df = df.groupBy("CustomerID", "Country") \
            .agg(
                sum_("TotalPrice").alias("Monetary"),
                count("*").alias("Frequency"),
                max_("InvoiceDate").alias("LastPurchaseRecency")
            ) \
            .orderBy(col("Monetary").desc())

        
        customer_data = [
            ("United Kingdom", "High"),
            ("Germany", "Medium"),
            ("France", "Low")
        ]
        customer_df = spark.createDataFrame(customer_data, ["Country", "CustomerTier"])

        joined_df = df.join(customer_df, "Country", "left")

        
        joined_df = joined_df.withColumn(
            "CustomerTier",
            coalesce(col("CustomerTier"), lit("Unknown"))
        )


        window_spec = Window.partitionBy("Country").orderBy(desc("TotalRevenue"))

        ranked_df = (
            joined_df
            .groupBy("Country", "StockCode", "Description", "CustomerTier")
            .agg(
                round(sum_("TotalPrice"), 2).alias("TotalRevenue"),
                count("*").alias("OrderCount")
            )
            .withColumn("Rank", row_number().over(window_spec))
            .filter(col("Rank") <= 5)
        )

        validate_spark_df(ranked_df, "ranked_products", min_rows=10)
        validate_spark_df(rfm_df, "customer_rfm", min_rows=100)

        ranked_df.write \
            .mode("overwrite") \
            .parquet(OUTPUT_PATH_1)

        logger.info("Saved ranked products to %s", OUTPUT_PATH_1)

        rfm_df.write \
            .mode("overwrite") \
            .parquet(OUTPUT_PATH_2)

        logger.info("Saved RFM data to %s",OUTPUT_PATH_2)

        spark.stop()

    except Exception as e:
        raise RuntimeError("PySpark transform failed: %s", e) from e


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error("PySpark transform failed: %s", e, exec_info=True)
        raise