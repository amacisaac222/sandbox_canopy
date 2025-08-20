# CanopyIQ AWS Terraform Module Outputs

# Application URLs
output "application_url" {
  description = "The URL of the CanopyIQ application"
  value       = "https://${var.domain_name}"
}

output "load_balancer_dns_name" {
  description = "The DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "load_balancer_zone_id" {
  description = "The zone ID of the load balancer"
  value       = aws_lb.main.zone_id
}

# Infrastructure
output "vpc_id" {
  description = "The VPC ID where resources are deployed"
  value       = local.vpc_id
}

output "subnet_ids" {
  description = "The subnet IDs where resources are deployed"
  value       = local.subnet_ids
}

output "availability_zones" {
  description = "The availability zones used"
  value       = local.azs
}

# ECS Resources
output "ecs_cluster_id" {
  description = "The ID of the ECS cluster"
  value       = aws_ecs_cluster.main.id
}

output "ecs_cluster_name" {
  description = "The name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "The name of the ECS service"
  value       = aws_ecs_service.app.name
}

output "ecs_task_definition_arn" {
  description = "The ARN of the ECS task definition"
  value       = aws_ecs_task_definition.app.arn
}

# Database
output "database_endpoint" {
  description = "The RDS instance endpoint"
  value       = aws_db_instance.main.endpoint
  sensitive   = true
}

output "database_port" {
  description = "The RDS instance port"
  value       = aws_db_instance.main.port
}

output "database_name" {
  description = "The name of the database"
  value       = aws_db_instance.main.db_name
}

output "database_username" {
  description = "The master username for the database"
  value       = aws_db_instance.main.username
  sensitive   = true
}

# Secrets Manager
output "db_credentials_secret_arn" {
  description = "The ARN of the database credentials secret"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "oidc_config_secret_arn" {
  description = "The ARN of the OIDC configuration secret"
  value       = var.create_secrets ? aws_secretsmanager_secret.oidc_config[0].arn : null
}

output "slack_config_secret_arn" {
  description = "The ARN of the Slack configuration secret"
  value       = var.create_secrets ? aws_secretsmanager_secret.slack_config[0].arn : null
}

# Security Groups
output "alb_security_group_id" {
  description = "The ID of the ALB security group"
  value       = aws_security_group.alb.id
}

output "ecs_security_group_id" {
  description = "The ID of the ECS security group"
  value       = aws_security_group.ecs.id
}

output "rds_security_group_id" {
  description = "The ID of the RDS security group"
  value       = aws_security_group.rds.id
}

# IAM Roles
output "ecs_task_execution_role_arn" {
  description = "The ARN of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  description = "The ARN of the ECS task role"
  value       = aws_iam_role.ecs_task.arn
}

# SSL Certificate
output "certificate_arn" {
  description = "The ARN of the SSL certificate"
  value       = local.certificate_arn
}

# CloudWatch
output "cloudwatch_log_group_name" {
  description = "The name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.app.name
}

output "cloudwatch_log_group_arn" {
  description = "The ARN of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.app.arn
}

# Auto Scaling (if enabled)
output "autoscaling_target_resource_id" {
  description = "The resource ID of the autoscaling target"
  value       = var.enable_auto_scaling ? aws_appautoscaling_target.ecs[0].resource_id : null
}

# DNS
output "route53_record_name" {
  description = "The Route53 record name"
  value       = aws_route53_record.app.name
}

output "route53_record_fqdn" {
  description = "The Route53 record FQDN"
  value       = aws_route53_record.app.fqdn
}

# Connection Information
output "database_connection_string" {
  description = "Database connection string (use with caution - contains credentials)"
  value       = "postgresql://${aws_db_instance.main.username}:${random_password.db_password.result}@${aws_db_instance.main.endpoint}:${aws_db_instance.main.port}/${aws_db_instance.main.db_name}"
  sensitive   = true
}

# Admin Panel URL
output "admin_panel_url" {
  description = "The URL of the CanopyIQ admin panel"
  value       = "https://${var.domain_name}/admin"
}

# Setup Wizard URL
output "setup_wizard_url" {
  description = "The URL of the CanopyIQ setup wizard (for first-time setup)"
  value       = "https://${var.domain_name}/setup"
}

# Environment Information
output "project_name" {
  description = "The project name used for resource naming"
  value       = var.project_name
}

output "environment" {
  description = "The environment name"
  value       = var.environment
}

output "region" {
  description = "The AWS region where resources are deployed"
  value       = data.aws_region.current.name
}

# Resource Counts and Limits
output "container_cpu" {
  description = "CPU units allocated to containers"
  value       = var.cpu
}

output "container_memory" {
  description = "Memory (MB) allocated to containers"
  value       = var.memory
}

output "ecs_desired_count" {
  description = "The desired number of ECS tasks"
  value       = var.desired_count
}

output "auto_scaling_enabled" {
  description = "Whether auto scaling is enabled"
  value       = var.enable_auto_scaling
}

output "auto_scaling_min_capacity" {
  description = "Minimum auto scaling capacity"
  value       = var.enable_auto_scaling ? var.min_capacity : null
}

output "auto_scaling_max_capacity" {
  description = "Maximum auto scaling capacity"
  value       = var.enable_auto_scaling ? var.max_capacity : null
}