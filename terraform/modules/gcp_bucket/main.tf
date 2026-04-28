resource "google_storage_bucket" "this" {
    name = var.bucket_name
    location = var.region
    force_destroy = var.force_destroy

    labels = var.labels
}

