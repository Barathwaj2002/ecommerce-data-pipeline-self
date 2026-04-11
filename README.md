# Ecommerce Data Pipeline — Self Built

End-to-end data pipeline project built in two phases without.

1. **Kubernetes-native pipeline** — local minikube, Airflow 3.x, PySpark, MongoDB, Spring Boot, Prometheus, Grafana
2. **GCP cloud-native pipeline** — GCS, Dataproc, BigQuery, dbt, Cloud Composer, GitHub Actions CI/CD

Both pipelines process the same ecommerce dataset (~500k records) from raw CSV to business-ready insights.

---

## Project Structure

ecommerce-data-pipeline-self/
├── .github/workflows/         # GitHub Actions CI/CD workflows
│   ├── ci.yml                 # Lint + syntax check + Docker build
│   ├── dbt-test.yml           # dbt deps + dbt test on push/PR
├── airflow-dags/              # Airflow DAGs and k8s job YAMLs
├── deployment/k8s/            # Kubernetes deployment manifests
├── deployment/ingestion/      # Ingestion Dockerfile
├── deployment/pyspark/        # PySpark Dockerfile
├── ecommerce_dbt/             # dbt project (staging, marts, tests, snapshots)
├── gcp_pipeline/              # GCP pipeline scripts and Composer DAG
├── processing/                # PySpark transformation scripts
├── storage/                   # MongoDB load scripts
└── docs/                      # Architecture diagrams

---

## Pipeline 1 — Kubernetes Native (Minikube)

### Overview

End-to-end pipeline running entirely on a local Kubernetes cluster using minikube.
Raw ecommerce CSV → PySpark transformations → MongoDB → Spring Boot REST API.
Orchestrated by Airflow 3.x standalone, monitored by Prometheus and Grafana.

### Architecture


Raw CSV (baked in ingestion image)
    ↓ [ingestion-job — Python/Pandas]
cleaned_data.parquet (PVC)
    ↓ [pyspark-job — PySpark]
day4_ranked_products.parquet + customer_rfm.parquet (PVC)
    ↓ [load-mongo-job — PyMongo]
MongoDB (ecommerce database)
    ↓ [ecommerce-api — Spring Boot]
REST API (/top-products, /customer-rfm)

Airflow 3.x (standalone) — orchestrates all jobs sequentially via BashOperator + kubectl
Prometheus + Grafana — monitors pipeline and Spring Boot metrics


### Architecture Diagram

ecommerce-data-pipeline-gcp/docs/architecture.drawio.png

### Sample Output

ecommerce-data-pipeline-gcp/docs/top-products-output.png

### Tech Stack

| Component | Technology |
|-----------|------------|
| Orchestration | Airflow 3.x standalone |
| Processing | PySpark 3.5 |
| Storage | MongoDB 8 |
| API | Spring Boot |
| Shared Storage | Kubernetes PVC |
| Monitoring | Prometheus + Grafana |
| Infrastructure | Minikube (docker driver), Docker, Kubernetes |
| Auth | RBAC ServiceAccount |

### How to Run

**Prerequisites:** minikube, kubectl, Docker

bash
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
# Open localhost:8080, trigger ecommerce_etl DAG

# 7. Access API
kubectl port-forward svc/ecommerce-api 8081:8081
# curl localhost:8081/api/insights/top-products


### Design Decisions

**Why emptyDir for Airflow DB and PVC for pipeline data?**
Airflow's SQLite DB only needs to be shared between containers in the same pod — emptyDir is sufficient and avoids unnecessary persistence. Pipeline parquet files need to survive across separate job pods running sequentially — PVC provides the shared persistent storage required.

**Why imagePullPolicy: Never?**
All images are built directly into minikube's Docker daemon using eval $(minikube docker-env). They don't exist on Docker Hub so Never prevents failed pull attempts from the registry.

**Why Airflow standalone?**
Single-node local dev — standalone runs scheduler, api-server, dag-processor, and triggerer in one pod. Simpler than managing separate Kubernetes Deployments for each Airflow component.

**Why RBAC ServiceAccount for Airflow?**
Airflow's BashOperator runs kubectl commands inside the pod to create and delete batch Jobs. Pods have no cluster permissions by default — a ServiceAccount with a Role bound to batch/jobs permissions grants exactly the access needed and nothing more.

**Why ClusterIP for MongoDB and LoadBalancer for API?**
MongoDB only needs to be reachable from inside the cluster (by pipeline jobs and the API). The Spring Boot API needs to be reachable from outside the cluster (browser, curl) — LoadBalancer exposes it externally.

### Challenges and Solutions

**Airflow 3.x JWT 403 auth on Kubernetes**
Problem: Task workers getting 403 Forbidden when communicating with api-server after pod restarts.
Root cause: emptyDir wiped the SQLite DB on every pod restart. Airflow generated a new random SECRET_KEY each time, causing JWT mismatch between the scheduler's task workers and the api-server.
Fix: Set a static AIRFLOW__CORE__SECRET_KEY environment variable across all containers — initContainer, webserver, and scheduler.

**WSL2 + minikube segfaults**
Problem: minikube ssh, minikube image load, and minikube profile list all segfaulted on WSL2.
Root cause: Old minikube install was using a VM-based driver which requires SSH into a VM — broken on WSL2.
Fix: Wiped minikube completely (docker rm -f minikube && docker volume rm minikube), reinstalled with --driver=docker. With the docker driver, minikube runs as a Docker container — no VM needed.

**Kubernetes DNS ExternalName conflict**
Problem: load-mongo-job failing with ServerSelectionTimeoutError: mongo:27017 Name or service not known.
Root cause: A stale ExternalName service named mongo was pointing to host.minikube.internal (leftover from docker-compose setup). The actual MongoDB pod had a different ClusterIP service.
Fix: Deleted the ExternalName service and reapplied the mongo deployment to create a proper ClusterIP service. DNS resolution of mongo then correctly pointed to the MongoDB pod.

**PySpark Python symlink in containers**
Problem: PySpark jobs failing with Cannot run program "/usr/bin/python" inside eclipse-temurin containers.
Root cause: eclipse-temurin installs Python as python3. Spark internally calls /usr/bin/python without the version suffix.
Fix: Added ln -s /usr/bin/python3 /usr/bin/python in the Dockerfile and set PYSPARK_PYTHON=/usr/bin/python3 env var in the Job YAML.

---

## Pipeline 2 — GCP Cloud Native

### Overview

Fully cloud-native pipeline on Google Cloud Platform.
Raw CSV (GCS) → PySpark on Dataproc → BigQuery → dbt transformation layer.
Orchestrated by Cloud Composer (managed Airflow on GKE).
CI/CD via GitHub Actions — lint, dbt tests, and Docker image builds on every push.

### Architecture


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
GitHub Actions runs lint + dbt tests on every push to main


### Architecture Diagram



### Sample BigQuery Output


+-----------+-------------------------------------+--------------------+------+
|  COUNTRY  |             DESCRIPTION             |    TOTALREVENUE    | RANK |
+-----------+-------------------------------------+--------------------+------+
| Australia | RABBIT NIGHT LIGHT                  |            3375.84 |    1 |
| Australia | SET OF 6 SPICE TINS PANTRY DESIGN   |             2082.0 |    2 |
| Austria   | POSTAGE                             |             1456.0 |    1 |
| Belgium   | POSTAGE                             |             4269.0 |    1 |
+-----------+-------------------------------------+--------------------+------+


### Tech Stack

| Component | Technology |
|-----------|------------|
| Orchestration | Cloud Composer 3 (managed Airflow + Cloud SQL PostgreSQL) |
| Storage | Google Cloud Storage |
| Processing | Dataproc PySpark (ephemeral cluster) |
| Data Warehouse | BigQuery (columnar, serverless) |
| Transformation | dbt-bigquery (staging, marts, tests, snapshots, seeds) |
| CI/CD | GitHub Actions |
| Auth | Application Default Credentials + Composer service account |

### How to Run

**Prerequisites:** gcloud CLI, Python 3.10+, dbt-bigquery

bash
# 1. Set up GCP project
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default login

# 2. Create GCS bucket and upload raw data
gcloud storage buckets create gs://YOUR_BUCKET --location=asia-south1
gcloud storage cp ingestion/raw_data/online_retail.csv gs://YOUR_BUCKET/raw/
gcloud storage cp gcp_pipeline/02_pyspark_transform.py gs://YOUR_BUCKET/scripts/

# 3. Run ingestion
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

# 7. Deploy via Cloud Composer (optional — incurs cost, delete after use)
gcloud composer environments create ecommerce-composer \
  --location=asia-south1 \
  --image-version=composer-3-airflow-2.10.5 \
  --environment-size=small

DAG_BUCKET=$(gcloud composer environments describe ecommerce-composer \
  --location=asia-south1 \
  --format="value(config.dagGcsPrefix)")

gcloud storage cp gcp_pipeline/cloud_composer/dags/gcp_etl_dag.py $DAG_BUCKET/
# Trigger from Composer Airflow UI, then delete environment
gcloud composer environments delete ecommerce-composer --location=asia-south1


### Design Decisions

**Why GCS instead of local storage?**
GCS integrates natively with Dataproc, BigQuery, and Composer — no credential management between services. Data written to GCS by one component is immediately available to the next without any transfer step.

**Why Dataproc instead of local PySpark?**
Scalable managed cluster with no Java/Python setup. Uses service account authentication automatically. Ephemeral pattern keeps costs near zero — cluster exists only for job duration.

**Why ephemeral cluster instead of permanent?**
Clusters bill by the hour even when idle. Ephemeral pattern — create, run, delete — means billing only for actual compute time. trigger_rule=ALL_DONE on the delete task guarantees the cluster is always deleted even if the job fails.

**Why BigQuery instead of PostgreSQL?**
BigQuery is columnar, serverless, and scales to petabytes automatically. PostgreSQL is row-oriented and requires manual scaling — not suitable for analytical workloads at this scale.

**Why dbt on top of BigQuery?**
dbt provides version-controlled transformations, data quality tests, documentation, and lineage tracking. Separates transformation logic from pipeline orchestration logic. Tests run automatically in CI on every push.

**Why Cloud Composer instead of standalone Airflow?**
Composer manages GKE, PostgreSQL metadata DB, DAG storage, and auto-scaling. No SECRET_KEY issues, no pod restarts wiping state. DAG deployment = copy a file to GCS — no image rebuild needed.

### Challenges and Solutions

**Pandas nanosecond to Spark microsecond timestamp incompatibility**
Problem: PySpark job failing with Illegal Parquet type: INT64 (TIMESTAMP(NANOS,false)).
Root cause: Pandas writes timestamps as nanoseconds by default. Dataproc's Spark 3.x only supports microsecond precision in Parquet files.
Fix: Added coerce_timestamps='us', allow_truncated_timestamps=True to df.to_parquet() in the ingestion script.

**GCP free tier CPU quota exhaustion**
Problem: Dataproc cluster creation failing silently with no clear error message.
Root cause: GCP free tier limits total CPUs to 12 across all regions. Cloud Composer's GKE cluster was already consuming most of the quota, leaving insufficient CPUs for Dataproc.
Fix: Checked IAM & Admin → Quotas & System Limits, identified the CPU quota limit, and selected a smaller machine type (e2-standard-2) that fit within remaining quota.

**Dataproc cluster naming convention violation**
Problem: Cluster creation failing with must match pattern (?:[a-z](?:[-a-z0-9]{0,49}[a-z0-9])?).
Root cause: Cluster name gcp_etl_dag-20260330 contained underscores. Dataproc cluster names only allow lowercase letters, numbers, and hyphens.
Fix: Changed cluster name to ecommerce-cluster-{{ ds_nodash }} — unique per DAG run, no underscores.

**dbt dependency conflict in Cloud Composer**
Problem: Installing dbt-bigquery in Composer failed due to conflicts with apache-airflow==2.10.5.
Root cause: dbt and Airflow share several Python dependencies with incompatible version requirements.
Fix: Documented the limitation. Production solution is to run dbt as an isolated Cloud Run Job triggered from Airflow via CloudRunJobOperator — keeps dbt dependencies completely separate from Airflow's environment.

### Known Limitations

- **Free tier CPU quota:** Max 12 vCPUs across all regions. Check IAM & Admin → Quotas & System Limits if cluster creation fails
- **Dataproc naming:** Cluster names must be lowercase with hyphens only — no underscores
- **Timestamp precision:** Use coerce_timestamps='us' when writing parquet for Spark consumption
- **dbt in Composer:** Dependency conflict with Airflow 2.10.5. Production solution: isolated Cloud Run Job

---

## CI/CD

Three GitHub Actions workflows:

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| ci.yml | Push to main | flake8 lint + Python syntax check, then Docker image build and push to Docker Hub |
| dbt-test.yml | Push + PR to main | Authenticates with GCP, runs dbt deps + dbt test against BigQuery |

Branch protection on main — PR required before merge, lint must pass.


- [Full Walkthrough — Kubernetes Pipeline (20 mins)](https://youtu.be/Bd0uvIslrLM)
- [Full Walkthrough — GCP Pipeline (15 mins)](https://youtu.be/J-wngmTopsQ)

---
## Certifications

- Google Cloud Certified Associate Cloud Engineer

## Author

Jayanth Barathwaj — [LinkedIn](https://linkedin.com/in/barathwaj8202) | [GitHub](https://github.com/Barathwaj2002)
