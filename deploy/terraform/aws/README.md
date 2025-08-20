# CanopyIQ AWS Terraform Module

This Terraform module deploys CanopyIQ on AWS using ECS Fargate with a complete infrastructure stack including:

- **ECS Fargate** service with auto-scaling
- **Application Load Balancer** with HTTPS (SSL/TLS)
- **RDS PostgreSQL** database with storage auto-scaling
- **AWS Secrets Manager** for sensitive configuration
- **CloudWatch Logs** for application logging
- **Security Groups** and **IAM roles** with least-privilege access
- **Route53 DNS** and **ACM SSL certificate**

## Architecture

```
Internet → Route53 → ALB (HTTPS) → ECS Fargate → RDS PostgreSQL
                      ↓
                 CloudWatch Logs
                      ↓
              AWS Secrets Manager
```

## Quick Start

1. **Prepare your domain**: Ensure you have a domain managed by Route53
2. **Deploy the infrastructure**:

```hcl
module "canopyiq" {
  source = "path/to/canopy/deploy/terraform/aws"
  
  domain_name = "canopyiq.yourdomain.com"
  
  # Optional: customize configuration
  environment = "prod"
  cpu         = 512
  memory      = 1024
}
```

3. **Configure secrets** in AWS Secrets Manager
4. **Access the setup wizard** at `https://yourdomain.com/setup`

## Examples

### Minimal Development Setup

See [`examples/simple/main.tf`](examples/simple/main.tf) for a complete example with minimal, cost-effective defaults.

```bash
cd examples/simple
terraform init
terraform plan -var="domain_name=canopyiq-dev.yourdomain.com"
terraform apply
```

### Production Setup

```hcl
module "canopyiq" {
  source = "path/to/canopy/deploy/terraform/aws"
  
  # Required
  domain_name = "canopyiq.yourdomain.com"
  
  # Production configuration
  environment           = "prod"
  cpu                  = 1024
  memory               = 2048
  desired_count        = 2
  db_instance_class    = "db.t3.small"
  
  # Security
  allowed_cidr_blocks = ["10.0.0.0/8", "172.16.0.0/12"]
  enable_deletion_protection = true
  
  # Scaling
  enable_auto_scaling = true
  min_capacity       = 2
  max_capacity       = 10
  
  # Backup and retention
  db_backup_retention_period = 30
  log_retention_days        = 30
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.0 |
| aws | ~> 5.0 |
| random | ~> 3.1 |

## Providers

| Name | Version |
|------|---------|
| aws | ~> 5.0 |
| random | ~> 3.1 |

## Prerequisites

1. **AWS CLI** configured with appropriate permissions
2. **Domain name** managed by Route53
3. **Docker image** for CanopyIQ available in a registry
4. **Terraform** installed (>= 1.0)

### Required AWS Permissions

The deploying user/role needs permissions for:
- ECS (cluster, service, task definition)
- EC2 (VPC, subnets, security groups)
- ELB (load balancers, target groups)
- RDS (instances, subnet groups)
- IAM (roles, policies)
- Secrets Manager (secrets)
- CloudWatch (log groups)
- Route53 (hosted zones, records)
- ACM (certificates)

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| domain_name | Domain name for the application | `string` | n/a | yes |
| project_name | Name of the project, used for resource naming | `string` | `"canopyiq"` | no |
| environment | Environment name (e.g., dev, staging, prod) | `string` | `"dev"` | no |
| container_image | Docker image for the CanopyIQ application | `string` | `"canopyiq/canopyiq:latest"` | no |
| cpu | CPU units for the ECS task (256, 512, 1024, 2048, 4096) | `number` | `256` | no |
| memory | Memory (MB) for the ECS task | `number` | `512` | no |
| db_instance_class | RDS instance class | `string` | `"db.t3.micro"` | no |
| allowed_cidr_blocks | CIDR blocks allowed to access the ALB | `list(string)` | `["0.0.0.0/0"]` | no |

See [`variables.tf`](variables.tf) for all available configuration options.

## Outputs

| Name | Description |
|------|-------------|
| application_url | The URL of the CanopyIQ application |
| admin_panel_url | The URL of the CanopyIQ admin panel |
| setup_wizard_url | The URL of the CanopyIQ setup wizard |
| database_endpoint | The RDS instance endpoint |
| db_credentials_secret_arn | The ARN of the database credentials secret |
| ecs_cluster_name | The name of the ECS cluster |

See [`outputs.tf`](outputs.tf) for all available outputs.

## Post-Deployment Configuration

### 1. Configure Secrets

After deployment, update the following secrets in AWS Secrets Manager:

#### OIDC Configuration
```json
{
  "issuer": "https://your-identity-provider.com",
  "client_id": "your-client-id",
  "client_secret": "your-client-secret"
}
```

#### Slack Configuration
```json
{
  "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
  "signing_secret": "your-slack-signing-secret"
}
```

### 2. Initial Setup

1. Visit the setup wizard at `https://yourdomain.com/setup`
2. Create the first admin user
3. Configure basic settings
4. Access the admin panel at `https://yourdomain.com/admin`

### 3. Monitoring

- **Application logs**: Available in CloudWatch Logs
- **Database metrics**: Available in RDS CloudWatch metrics
- **Application metrics**: Available at `https://yourdomain.com/metrics` (Prometheus format)

## Cost Optimization

### Development Environment
```hcl
cpu                   = 256
memory               = 512
db_instance_class    = "db.t3.micro"
desired_count        = 1
log_retention_days   = 3
db_backup_retention_period = 3
```

### Production Environment
```hcl
cpu                   = 1024
memory               = 2048
db_instance_class    = "db.t3.small"
desired_count        = 2
log_retention_days   = 30
db_backup_retention_period = 30
enable_deletion_protection = true
```

## Security Considerations

1. **Network Security**: Restrict `allowed_cidr_blocks` in production
2. **Database Security**: RDS is deployed in private subnets only
3. **Secrets Management**: All sensitive data stored in AWS Secrets Manager
4. **SSL/TLS**: HTTPS enforced with HTTP redirect
5. **IAM**: Least-privilege access roles

## Troubleshooting

### Common Issues

#### Certificate Validation Fails
- Ensure the domain is managed by Route53
- Check DNS propagation
- Verify hosted zone permissions

#### ECS Tasks Failing to Start
- Check CloudWatch logs for error messages
- Verify secrets are properly configured
- Ensure container image is accessible

#### Database Connection Issues
- Verify security group rules
- Check database credentials in secrets
- Ensure RDS instance is running

### Useful Commands

```bash
# View application logs
aws logs tail /ecs/canopyiq-dev --follow

# Check ECS service status
aws ecs describe-services --cluster canopyiq-dev --services canopyiq-dev

# Test database connectivity
aws rds describe-db-instances --db-instance-identifier canopyiq-dev

# View secrets
aws secretsmanager get-secret-value --secret-id canopyiq-dev-db-credentials
```

## Contributing

When modifying this module:

1. Update variable descriptions and defaults
2. Add new outputs for important resources
3. Update this README with new configuration options
4. Test with the example configuration
5. Ensure backwards compatibility

## License

This module is part of the CanopyIQ project. See the main project license for details.