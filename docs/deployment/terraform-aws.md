# Terraform (AWS)

Module provisions:
- ECS Fargate service
- ALB + ACM TLS
- RDS Postgres
- Secrets Manager (OIDC, Slack)
- CloudWatch logs

See: `deploy/terraform/aws/examples/simple/main.tf`