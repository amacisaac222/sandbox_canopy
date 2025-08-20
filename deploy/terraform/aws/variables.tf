# CanopyIQ AWS Terraform Module Variables

variable "project_name" {
  description = "Name of the project, used for resource naming"
  type        = string
  default     = "canopyiq"
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

# Networking
variable "vpc_id" {
  description = "VPC ID to deploy resources into. If not provided, uses default VPC"
  type        = string
  default     = ""
}

variable "subnet_ids" {
  description = "List of subnet IDs for ECS service and ALB. If empty, uses default subnets"
  type        = list(string)
  default     = []
}

variable "availability_zones" {
  description = "List of availability zones. If empty, uses first 2 AZs in region"
  type        = list(string)
  default     = []
}

# Domain and SSL
variable "domain_name" {
  description = "Domain name for the application (e.g., canopyiq.example.com)"
  type        = string
}

variable "hosted_zone_id" {
  description = "Route53 hosted zone ID for the domain. If empty, will look up automatically"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN. If empty, will create a new certificate"
  type        = string
  default     = ""
}

# Container Configuration
variable "container_image" {
  description = "Docker image for the CanopyIQ application"
  type        = string
  default     = "canopyiq/canopyiq:latest"
}

variable "container_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8080
}

variable "cpu" {
  description = "CPU units for the ECS task (256, 512, 1024, 2048, 4096)"
  type        = number
  default     = 256
}

variable "memory" {
  description = "Memory (MB) for the ECS task"
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

variable "health_check_path" {
  description = "Health check path for ALB target group"
  type        = string
  default     = "/health"
}

# Database Configuration
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "Initial allocated storage for RDS instance (GB)"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for RDS autoscaling (GB)"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "canopyiq"
}

variable "db_username" {
  description = "Master username for the PostgreSQL database"
  type        = string
  default     = "canopyiq"
}

variable "db_backup_retention_period" {
  description = "Number of days to retain database backups"
  type        = number
  default     = 7
}

variable "db_backup_window" {
  description = "Preferred backup window for RDS"
  type        = string
  default     = "03:00-04:00"
}

variable "db_maintenance_window" {
  description = "Preferred maintenance window for RDS"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

# Secrets Configuration
variable "secrets_prefix" {
  description = "Prefix for AWS Secrets Manager secret names"
  type        = string
  default     = ""
}

variable "create_secrets" {
  description = "Whether to create placeholder secrets in AWS Secrets Manager"
  type        = bool
  default     = true
}

# Security Configuration
variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access the ALB"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "enable_deletion_protection" {
  description = "Enable deletion protection for RDS and ALB"
  type        = bool
  default     = false
}

# Logging Configuration
variable "log_retention_days" {
  description = "CloudWatch log retention period in days"
  type        = number
  default     = 7
}

# Auto Scaling Configuration
variable "enable_auto_scaling" {
  description = "Enable auto scaling for ECS service"
  type        = bool
  default     = true
}

variable "min_capacity" {
  description = "Minimum number of ECS tasks"
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "Maximum number of ECS tasks"
  type        = number
  default     = 4
}

variable "cpu_threshold" {
  description = "CPU utilization threshold for auto scaling"
  type        = number
  default     = 70
}

variable "memory_threshold" {
  description = "Memory utilization threshold for auto scaling"
  type        = number
  default     = 80
}

# Tags
variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}