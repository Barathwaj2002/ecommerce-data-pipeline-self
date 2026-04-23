variable "project_id" {
    description = "GCP Project ID"
    type = string
}

variable "region" {
    description = "GCP Region"
    type = string
    default = "asia-south1"
}

variable "bucket_name" {
    description = "GCP Bucket name"
    type = string
}