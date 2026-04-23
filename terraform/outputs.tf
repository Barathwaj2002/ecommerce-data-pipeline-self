output "bucket_name" {
    value = google_storage_bucket.pipeline_bucket.name
}

output "dataset_id" {
    value = google_bigquery_dataset.ecommerce.dataset_id
}

output "service_account_email" {
    value = google_service_account.pipeline_sa.email
}