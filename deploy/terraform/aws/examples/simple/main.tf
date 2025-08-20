# Simple CanopyIQ Deployment Example
#
# This example shows how to deploy CanopyIQ using the minimal defaults
# for a development or small production environment.

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Configure the AWS Provider
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Owner       = "DevOps Team"
      Environment = var.environment
      Project     = "CanopyIQ"
      Terraform   = "true"
    }
  }
}

# Variables for this example
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  # Example: "canopyiq-dev.yourdomain.com"
}

variable "container_image" {
  description = "Docker image for CanopyIQ"
  type        = string
  default     = "canopyiq/canopyiq:latest"
  # You can also use:
  # - A public registry: "your-org/canopyiq:v1.0.0"
  # - ECR: "123456789012.dkr.ecr.us-west-2.amazonaws.com/canopyiq:latest"
}

# Deploy CanopyIQ using the module
module "canopyiq" {
  # Path to the module (adjust if using from a different location)
  source = "../.."

  # Required variables
  domain_name = var.domain_name

  # Basic configuration
  project_name     = "canopyiq"
  environment      = var.environment
  region          = var.aws_region
  container_image = var.container_image

  # Small, cost-effective configuration for development
  cpu                    = 256    # 0.25 vCPU
  memory                = 512    # 512 MB
  desired_count         = 1      # Single instance
  db_instance_class     = "db.t3.micro"  # Small RDS instance
  db_allocated_storage  = 20     # 20GB storage
  
  # Auto scaling (enabled but conservative)
  enable_auto_scaling = true
  min_capacity       = 1
  max_capacity       = 3
  cpu_threshold      = 75
  memory_threshold   = 85

  # Security (restrictive for development)
  allowed_cidr_blocks = ["0.0.0.0/0"]  # CHANGE THIS for production!
  
  # Backup and retention (minimal for cost savings)
  db_backup_retention_period = 3    # 3 days
  log_retention_days        = 3    # 3 days
  
  # Deletion protection (disabled for easier cleanup in dev)
  enable_deletion_protection = false

  # Additional tags
  tags = {
    Owner        = "DevOps Team"
    CostCenter   = "Engineering"
    Application  = "CanopyIQ"
  }
}

# Outputs from the module
output "application_url" {
  description = "The URL where CanopyIQ is accessible"
  value       = module.canopyiq.application_url
}

output "admin_panel_url" {
  description = "The URL for the CanopyIQ admin panel"
  value       = module.canopyiq.admin_panel_url
}

output "setup_wizard_url" {
  description = "The URL for first-time setup (if no admin users exist)"
  value       = module.canopyiq.setup_wizard_url
}

output "database_endpoint" {
  description = "Database endpoint (sensitive)"
  value       = module.canopyiq.database_endpoint
  sensitive   = true
}

output "secrets_to_configure" {
  description = "AWS Secrets Manager secrets that need to be configured"
  value = {
    oidc_config  = module.canopyiq.oidc_config_secret_arn
    slack_config = module.canopyiq.slack_config_secret_arn
  }
}

output "cloudwatch_logs" {
  description = "CloudWatch log group for application logs"
  value       = module.canopyiq.cloudwatch_log_group_name
}

# Example of how to access the secrets after deployment
output "next_steps" {
  description = "Next steps after deployment"
  value = <<-EOT
    🚀 CanopyIQ has been deployed successfully!

    Next steps:
    1. Visit the setup wizard: ${module.canopyiq.setup_wizard_url}
    2. Configure secrets in AWS Secrets Manager:
       - OIDC config: ${module.canopyiq.oidc_config_secret_arn}
       - Slack config: ${module.canopyiq.slack_config_secret_arn}
    3. Access the application: ${module.canopyiq.application_url}
    4. Admin panel: ${module.canopyiq.admin_panel_url}
    5. Monitor logs: aws logs tail ${module.canopyiq.cloudwatch_log_group_name} --follow

    Security Note: Update allowed_cidr_blocks in production!
  EOT
}