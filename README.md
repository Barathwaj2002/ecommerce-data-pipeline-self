# Ecommerce Data Pipeline — Self Built

End-to-end data pipeline project built in two phases:
1. **Kubernetes-native pipeline** on local minikube
2. **Cloud-native GCP pipeline** on Google Cloud Platform

Both pipelines process the same ecommerce dataset (~500k records) from raw CSV to business-ready insights.

---

## Project Structure
```
ecommerce-data-pipeline-self/
├── airflow-dags/          # Airflow DAGs and k8s job YAMLs
├── deployment/k8s/        # Kubernetes deployment manifests
├── deployment/pyspark/    # PySpark Dockerfile
├── ecommerce_dbt/         # dbt project (staging, marts, tests, snapshots)
├── gcp_pipeline/          # GCP pipeline scripts and Composer DAG
├── processing/            # PySpark transformation scripts
├── storage/               # MongoDB load scripts
└── docs/                  # Architecture diagrams
```

---

## Pipeline 1 — Kubernetes Native (Minikube)

### Overview
End-to-end pipeline running entirely on a local Kubernetes cluster using minikube.
Raw ecommerce CSV → PySpark transformations → MongoDB → Spring Boot REST API.
Orchestrated by Airflow 3.x standalone, monitored by Prometheus and Grafana.

### Architecture
```
Raw CSV (baked in ingestion image)
    ↓ [ingestion-job — Python/Pandas]
cleaned_data.parquet (PVC)
    ↓ [pyspark-job — PySpark]
day4_ranked_products.parquet + customer_rfm.parquet (PVC)
    ↓ [load-mongo-job — PyMongo]
MongoDB (ecommerce database)
    ↓ [ecommerce-api — Spring Boot]
REST API (/top-products, /customer-rfm)

Airflow 3.x (standalone) — orchestrates all jobs sequentially
Prometheus + Grafana — monitors pipeline and Spring Boot metrics
```

### Tech Stack
- **Orchestration:** Airflow 3.x standalone (scheduler + api-server + dag-processor in one pod)
- **Processing:** PySpark 3.5 (product revenue ranking, customer RFM analysis)
- **Storage:** MongoDB 8 (ClusterIP service, emptyDir volume)
- **API:** Spring Boot (REST endpoints with pagination and sorting)
- **Shared storage:** Kubernetes PersistentVolumeClaim (parquet handoff between jobs)
- **Monitoring:** Prometheus + Grafana (anonymous admin, k8s service discovery)
- **Infrastructure:** Minikube (docker driver), Docker, Kubernetes Jobs and Deployments
- **Auth:** RBAC ServiceAccount granting Airflow pod permission to create/delete Jobs

### How to Run

**Prerequisites:** minikube, kubectl, Docker
```bash
# 1. Start minikube with docker driver
minikube start --driver=docker

# 2. Point shell at minikube's Docker daemon
eval $(minikube docker-env)

# 3. Build all images
docker build -t ecommerce-api:spring deployment/ecommerce-api/
docker build -t ingestion:latest -f deployment/ingestion/Dockerfile .
docker build -t pyspark:latest -f deployment/pyspark/Dockerfile .
docker build -t airflow-custom:latest -f Dockerfile.airflow .

# 4. Apply Kubernetes manifests
kubectl apply -f deployment/k8s/pvc.yml
kubectl apply -f deployment/k8s/mongo-deployment.yml
kubectl apply -f deployment/k8s/api-deployment.yml
kubectl apply -f deployment/k8s/prometheus-config.yml
kubectl apply -f deployment/k8s/prometheus-deployment.yml
kubectl apply -f deployment/k8s/grafana-deployment.yml
kubectl apply -f deployment/k8s/airflow-rbac.yml
kubectl apply -f deployment/k8s/airflow-deployment.yml

# 5. Wait for pods to be ready
kubectl get pods -w

# 6. Access Airflow UI
kubectl port-forward svc/airflow-webserver 8080:8080
# Open localhost:8080

# 7. Reserialize DAGs and trigger
kubectl exec -it deployment/airflow-webserver -- airflow dags reserialize
# Trigger ecommerce_etl DAG from UI
```

### Design Decisions

**Why emptyDir for Airflow DB and PVC for pipeline data?**
Airflow's SQLite DB only needs to be shared between containers in the same pod — emptyDir is sufficient. Pipeline parquet files need to persist across separate job pods — PVC is required.

**Why imagePullPolicy: Never?**
All images are built directly into minikube's Docker daemon using `eval $(minikube docker-env)`. They don't exist on Docker Hub so Never prevents failed pull attempts.

**Why Airflow standalone?**
Single-node local dev — standalone runs scheduler, api-server, dag-processor and triggerer in one pod. Simpler than managing separate deployments for each component.

**Why RBAC ServiceAccount for Airflow?**
Airflow's BashOperator runs `kubectl` commands to create/delete Jobs. Pods don't have cluster permissions by default — ServiceAccount with a Role bound to batch/jobs permissions is required.

**Why ClusterIP for MongoDB and LoadBalancer for API?**
MongoDB only needs to be reachable from inside the cluster. API needs to be reachable from outside (browser, curl) — LoadBalancer exposes it externally.

### Known Issues and Fixes
- **WSL2 + minikube:** Use `--driver=docker` to avoid VM segfaults
- **Airflow 3.x 403 auth:** Set static `AIRFLOW__CORE__SECRET_KEY` env var — emptyDir wipes SQLite on restart causing JWT mismatch
- **ExternalName mongo service:** Delete and recreate as ClusterIP if DNS resolution fails from job pods
- **PySpark python symlink:** `eclipse-temurin` base image needs `ln -s /usr/bin/python3 /usr/bin/python`

---

## Pipeline 2 — GCP Cloud Native

### Overview
Fully cloud-native pipeline on Google Cloud Platform.
Raw CSV (GCS) → PySpark on Dataproc → BigQuery → dbt transformation layer.
Orchestrated by Cloud Composer (managed Airflow on GKE).

### Architecture
```
Raw CSV (GCS: bucket/raw/)
    ↓ [Airflow ingestion task — pandas]
Cleaned Parquet (GCS: bucket/processed/)
    ↓ [Dataproc PySpark job — ephemeral cluster]
Ranked Products + Customer RFM Parquets (GCS: bucket/processed/)
    ↓ [Airflow load_to_bq task — BigQuery client]
BigQuery Tables (ecommerce_data dataset)
    ↓ [dbt — staging models + mart models]
BigQuery Views/Tables (ecommerce_dbt_dev dataset)

Cloud Composer orchestrates the full pipeline via DAG
```

### Tech Stack
- **Orchestration:** Cloud Composer 3 (managed Airflow on GKE with Cloud SQL PostgreSQL)
- **Storage:** Google Cloud Storage (raw data, processed parquets, scripts, DAGs)
- **Processing:** Dataproc PySpark (ephemeral cluster, product ranking + RFM analysis)
- **Data Warehouse:** BigQuery (columnar, serverless, partitioned)
- **Transformation:** dbt-bigquery (staging models, mart models, tests, snapshots, seeds)
- **Auth:** Application Default Credentials + Composer service account (no JSON keys)

### How to Run

**Prerequisites:** gcloud CLI, Python 3.10+, dbt-bigquery
```bash
# 1. Set up GCP project
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default login

# 2. Create GCS bucket and upload raw data
gcloud storage buckets create gs://YOUR_BUCKET --location=asia-south1
gcloud storage cp ingestion/raw_data/online_retail.csv gs://YOUR_BUCKET/raw/
gcloud storage cp gcp_pipeline/02_pyspark_transform.py gs://YOUR_BUCKET/scripts/

# 3. Run ingestion locally (or via Composer)
python3 gcp_pipeline/01_ingest_gcs.py

# 4. Create Dataproc cluster and run PySpark
gcloud dataproc clusters create ecommerce-cluster \
  --region=asia-south1 \
  --master-machine-type=e2-standard-4 \
  --master-boot-disk-size=50GB \
  --image-version=2.2-debian12

gcloud dataproc jobs submit pyspark \
  gs://YOUR_BUCKET/scripts/02_pyspark_transform.py \
  --cluster=ecommerce-cluster \
  --region=asia-south1

gcloud dataproc clusters delete ecommerce-cluster --region=asia-south1

# 5. Load to BigQuery
python3 gcp_pipeline/03_load_bigquery.py

# 6. Run dbt
cd ecommerce_dbt
dbt deps
dbt build

# 7. (Optional) Deploy via Cloud Composer
gcloud composer environments create ecommerce-composer \
  --location=asia-south1 \
  --image-version=composer-3-airflow-2.10.5 \
  --environment-size=small

DAG_BUCKET=$(gcloud composer environments describe ecommerce-composer \
  --location=asia-south1 \
  --format="value(config.dagGcsPrefix)")

gcloud storage cp gcp_pipeline/cloud_composer/dags/gcp_etl_dag.py $DAG_BUCKET/
# Trigger from Composer Airflow UI
# Delete Composer after use to avoid billing
gcloud composer environments delete ecommerce-composer --location=asia-south1
```

### Design Decisions

**Why GCS instead of local storage?**
GCS integrates natively with Dataproc, BigQuery, and Composer — no credential management needed between services. Reliable, cheap, globally accessible.

**Why Dataproc instead of local PySpark?**
Scalable managed cluster — no Java/Python setup hassles. Uses service account authentication automatically. Ephemeral pattern keeps costs near zero.

**Why ephemeral cluster instead of permanent?**
Cluster bills by the hour even when idle. Ephemeral pattern — create, run job, delete — means billing only for actual compute time. Enforced via `trigger_rule=ALL_DONE` on delete task so cluster is always deleted even on failures.

**Why BigQuery instead of PostgreSQL?**
BigQuery is columnar, serverless, and scales to petabytes automatically. PostgreSQL is row-oriented and requires manual scaling — not suitable for analytical workloads at scale.

**Why dbt on top of BigQuery?**
dbt provides version-controlled transformations, data quality tests, documentation, and lineage tracking on top of raw BigQuery tables. Separates transformation logic from pipeline logic.

**Why Cloud Composer instead of standalone Airflow?**
Composer manages GKE, PostgreSQL metadata DB, DAG storage, and auto-scaling. No SECRET_KEY issues, no pod restarts wiping state. DAG deployment = copy file to GCS.

### Known Limitations
- **Free tier CPU quota:** Max 12 vCPUs across all regions. Check IAM & Admin → Quotas & System Limits if cluster creation fails
- **Dataproc naming:** Cluster names must be lowercase with hyphens only — no underscores
- **Timestamp precision:** Pandas writes nanosecond timestamps by default. Use `coerce_timestamps='us'` when writing parquet for Spark consumption
- **dbt in Composer:** dbt and Airflow 2.10.5 have dependency conflicts. Production solution is to run dbt in an isolated Cloud Run Job triggered from Airflow

---

## Certifications
- Google Cloud Associate Cloud Engineer

## Author
Jayanth Barathwaj — [LinkedIn](https://linkedin.com/in/barathwaj8202) | [GitHub](https://github.com/Barathwaj2002)