import pandas as pd
from pathlib import Path

# Base directory: ingestion/
BASE_DIR = Path(__file__).resolve().parent

# Paths (relative to ingestion/)
RAW_DATA_PATH = BASE_DIR / "raw_data" / "online_retail.csv"
CLEANED_DATA_PATH = BASE_DIR / "processed_data" / "cleaned_data.parquet"


def load_raw_data(file_path: Path) -> pd.DataFrame:
    print(f"Loading e-commerce data from {file_path}...")
    df = pd.read_csv(file_path, encoding="ISO-8859-1")
    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    print("Columns:", df.columns.tolist())
    print("\nSample (first 5 rows):")
    print(df.head())
    return df


def basic_cleaning(df: pd.DataFrame) -> pd.DataFrame:
    print("Applying basic cleaning...")
    
    df = df.dropna(subset=["CustomerID"])    
    df = df[df["Quantity"] > 0]              

    # Ensure datetime first
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])

    # Fix timestamp precision for Spark compatibility
    df["InvoiceDate"] = df["InvoiceDate"].astype("datetime64[us]")

    print(f"After cleaning: {len(df)} rows")
    return df


def save_cleaned(df: pd.DataFrame, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_parquet(
        output_path,
        index=False,
        engine="pyarrow",
        coerce_timestamps="us",
        allow_truncated_timestamps=True
    )

    print(f"Cleaned data saved to {output_path}")


if __name__ == "__main__":
    df = load_raw_data(RAW_DATA_PATH)
    df_clean = basic_cleaning(df)
    save_cleaned(df_clean, CLEANED_DATA_PATH)
