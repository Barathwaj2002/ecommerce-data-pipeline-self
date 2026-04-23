resource "google_storage_bucket" "pipeline_bucket" {
    name = var.bucket_name
    location = var.region
    force_destroy = true

    labels = {
        environment = "dev"
        project = "ecommerce-pipeline"
    }
}

resource "google_bigquery_dataset" "ecommerce" {
    dataset_id = "ecommerce_tf"
    location = var.region
}

resource "google_service_account" "pipeline_sa" {
    account_id = "pipeline-sa-tf"
    display_name = "Pipeline Service Account (Terraform)"
}

resource "google_project_iam_member" "bq_editor" {
    project = var.project_id
    role = "roles/bigquery.dataEditor"
    member = "serviceAccount:${google_service_account.pipeline_sa.email}"
}
