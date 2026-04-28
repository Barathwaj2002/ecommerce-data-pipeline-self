terraform{
    required_providers{
        google = {
            source = "hashicorp/google"
            version = "~> 5.0"
        }
    }

    backend "gcs" {
        bucket = "ecommerce-tf-state-bucket"
        prefix = "terraform/state"
    }
}

provider "google"{
    project = var.project_id
    region = var.region
}

module "pipeline_bucket"{
    source = "./modules/gcp_bucket"
    bucket_name = var.bucket_name
    region = var.region
    labels = {
        environment = "dev"
        project = "ecommerce-pipeline"
    }
}

module "ecommerce_dataset"{
    source = "./modules/big_query"
    dataset_id = "ecommerce_tf"
    region = var.region
}