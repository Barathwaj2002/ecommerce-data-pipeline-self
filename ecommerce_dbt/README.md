# ecommerce_dbt

dbt project for the GCP cloud-native ecommerce pipeline. Transforms raw BigQuery tables into analytics-ready models with data quality tests, snapshots, and documentation.

---

## Project Structure


ecommerce_dbt/
├── models/
│   ├── staging/
│   │   ├── sources.yml              # Source definitions (raw BigQuery tables)
│   │   ├── schema.yml               # Model tests and column descriptions
│   │   ├── stg_product_revenue.sql  # Staging model — product revenue
│   │   └── stg_customer_rfm.sql     # Staging model — customer RFM
│   └── marts/
│       ├── country_performance.sql  # Country-level product + customer analysis
│       └── country_tier_analysis.sql # Country performance joined with tier mapping
├── macros/
│   └── clean_string.sql             # Reusable macro — TRIM + UPPER on string columns
├── seeds/
│   └── customer_tier_mapping.csv    # Reference data — country to tier mapping
├── snapshots/
│   └── customer_rfm_snapshot.sql    # SCD Type 2 snapshot tracking RFM changes
├── tests/
│   ├── assert_product_rank_max_5.sql    # Singular test — no rank > 5
│   └── assert_no_negative_revenue.sql  # Singular test — no negative revenue
├── packages.yml                     # dbt_utils + dbt_expectations
├── profiles.yml                     # BigQuery connection config
└── dbt_project.yml                  # Project config


---

## Data Flow


BigQuery: ecommerce_data.product_revenue  (raw)
BigQuery: ecommerce_data.customer_rfm     (raw)
    ↓ [source()]
stg_product_revenue  (staging view — renamed, cast, cleaned)
stg_customer_rfm     (staging view — renamed, cast, deduplicated)
    ↓ [ref()]
country_performance       (mart table — top product per country + customer metrics)
country_tier_analysis     (mart table — country performance + tier from seed)


---

## Models

### Staging

**stg_product_revenue**
Thin wrapper over raw product_revenue table. Renames Rank to ProductRank, rounds TotalRevenue, applies clean_string macro to Country and Description.

**stg_customer_rfm**
Thin wrapper over raw customer_rfm table. Casts CustomerId to INT64, rounds Monetary. Deduplicates on CustomerId keeping highest spend record using QUALIFY ROW_NUMBER().

### Marts

**country_performance**
Joins top-ranked product per country (from stg_product_revenue where ProductRank = 1) with aggregated customer metrics (count, avg spend, avg frequency) from stg_customer_rfm. Generates surrogate key using dbt_utils.generate_surrogate_key.

**country_tier_analysis**
Extends country_performance by joining with the customer_tier_mapping seed to add Tier and Region columns per country.

---

## Tests

### Schema tests (schema.yml)
- not_null on key columns across both staging models
- unique on CustomerId in stg_customer_rfm
- dbt_expectations.expect_column_values_to_be_between on TotalRevenue, ProductRank, Monetary, Frequency
- dbt_expectations.expect_column_value_lengths_to_be_between on Country

### Singular tests
- assert_product_rank_max_5.sql — fails if any product has rank > 5
- assert_no_negative_revenue.sql — fails if any TotalRevenue is negative

---

## Snapshots

**customer_rfm_snapshot**
SCD Type 2 snapshot tracking changes in customer Monetary and Frequency over time.
- Strategy: timestamp using LastPurchaseRecency
- Adds dbt_valid_from, dbt_valid_to, dbt_updated_at, dbt_scd_id columns
- dbt_valid_to = NULL indicates the currently active record

---

## Packages

- dbt-labs/dbt_utils — surrogate key generation, utility macros
- calogica/dbt_expectations — Great Expectations-style data quality tests

---

## How to Run

**Prerequisites:** Python 3.10+, dbt-bigquery, GCP ADC configured

bash
# Install dbt
pip install dbt-bigquery

# Install packages
dbt deps

# Run all models
dbt run

# Run tests
dbt test

# Run snapshots
dbt snapshot

# Run everything in dependency order
dbt build

# Generate and view documentation
dbt docs generate
dbt docs serve
# Open localhost:8080 to view lineage graph


---

## Lineage Graph

<!-- INSERT: Screenshot of dbt docs lineage graph -->

---

## CI/CD

dbt tests run automatically via GitHub Actions on every push and pull request to main.
See .github/workflows/dbt-test.yml in the root repo.

**Known limitation:** dbt cannot be installed inside Cloud Composer due to dependency conflicts with Airflow 2.10.5. In production this would run as an isolated Cloud Run Job triggered from the Composer DAG via CloudRunJobOperator.
