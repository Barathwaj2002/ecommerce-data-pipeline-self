variable "bucket_name"{
    type = string
}

variable "region"{
    type = string
}

variable "force_destroy"{
    type = bool
    default = true
}

variable "labels"{
    type = map(string)
    default = {}
}