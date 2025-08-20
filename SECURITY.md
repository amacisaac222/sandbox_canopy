# Security Policy

## Reporting Security Vulnerabilities

We take the security of CanopyIQ seriously. If you discover a security vulnerability, please follow responsible disclosure practices.

### How to Report

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report security vulnerabilities via:

- **Email**: security@canopyiq.ai
- **Security Portal**: [https://canopyiq.ai/security/report](https://canopyiq.ai/security/report)
- **PGP Encrypted Email**: Use our PGP key (Key ID: `0x1234567890ABCDEF`)

### What to Include

Please include the following information in your report:

1. **Description**: A clear description of the vulnerability
2. **Impact**: The potential impact and affected components
3. **Reproduction Steps**: Detailed steps to reproduce the issue
4. **Environment**: Version numbers, deployment configuration, etc.
5. **Supporting Materials**: Screenshots, logs, or proof-of-concept code (if applicable)

### Response Timeline

- **Initial Response**: Within 24 hours of report submission
- **Vulnerability Assessment**: Within 72 hours of initial response
- **Status Updates**: Every 5 business days until resolution
- **Fix Timeline**: Critical issues resolved within 7 days, high priority within 30 days

### Security Vulnerability Classification

We use the following severity levels based on CVSS 3.1:

- **Critical (9.0-10.0)**: Immediate attention, emergency patches
- **High (7.0-8.9)**: Next scheduled release or out-of-band patch
- **Medium (4.0-6.9)**: Regular release cycle
- **Low (0.1-3.9)**: Regular release cycle or documentation update

### Disclosure Policy

- **Coordinated Disclosure**: We follow responsible disclosure practices
- **Public Disclosure**: After fix is available and users have had time to update
- **Security Advisory**: Published on GitHub Security Advisories
- **CVE Assignment**: For qualifying vulnerabilities

### Recognition

We maintain a security hall of fame to recognize security researchers who help improve CanopyIQ's security:

- Responsible disclosure researchers will be credited in release notes
- Acknowledgment in our security advisories (unless you prefer to remain anonymous)
- Swag and recognition for significant findings

## Security Features

### Built-in Security Controls

- **Policy Enforcement**: Local and centralized policy evaluation
- **Audit Logging**: Comprehensive logging of all agent actions
- **Role-Based Access Control (RBAC)**: Fine-grained permissions
- **Encryption**: TLS 1.3 in transit, KMS encryption at rest
- **Secret Management**: Integration with enterprise secret stores
- **Network Isolation**: Air-gapped deployment support

### Security Hardening

- **Container Security**: Non-root containers, read-only filesystems
- **Network Policies**: Kubernetes NetworkPolicy support
- **Resource Limits**: CPU, memory, and storage quotas
- **Security Scanning**: Regular vulnerability scanning of dependencies
- **Static Analysis**: SAST integration in CI/CD pipeline

## Compliance and Certifications

- **SOC 2 Type II**: In progress
- **ISO 27001**: Planned for 2024
- **HIPAA**: BAA available for healthcare customers
- **PCI DSS**: For payment processing use cases
- **GDPR**: Privacy-by-design architecture

## Security Contact Information

- **Security Team**: security@canopyiq.ai
- **General Contact**: contact@canopyiq.ai
- **Business Hours**: Monday-Friday, 9 AM - 6 PM UTC
- **Emergency Contact**: +1-555-CANOPY-SEC (24/7 for critical issues)

## Security Resources

- **Security Whitepaper**: [docs/security-whitepaper.md](docs/security-whitepaper.md)
- **Deployment Security**: [helm/canopyiq/README.md](helm/canopyiq/README.md)
- **AWS Security**: [deploy/terraform/aws/README.md](deploy/terraform/aws/README.md)
- **Security Blog**: [https://blog.canopyiq.ai/security](https://blog.canopyiq.ai/security)

## Supported Versions

We provide security updates for the following versions:

| Version | Supported          | End of Life    |
| ------- | ------------------ | -------------- |
| 1.x.x   | ✅ Full support    | TBD            |
| 0.9.x   | ⚠️ Security only   | 2024-12-31     |
| < 0.9   | ❌ No support      | 2024-06-30     |

## Security Development Lifecycle

- **Threat Modeling**: Conducted for all major features
- **Secure Code Review**: Required for all code changes
- **Dependency Scanning**: Automated scanning for known vulnerabilities
- **Penetration Testing**: Annual third-party security assessments
- **Security Training**: Regular training for all development team members

## Additional Resources

- **NIST Cybersecurity Framework**: We align with NIST CSF guidelines
- **OWASP Top 10**: Regular assessment against OWASP recommendations
- **CIS Controls**: Implementation of CIS security controls
- **MITRE ATT&CK**: Threat modeling using MITRE ATT&CK framework

---

**Last Updated**: 2024-01-15  
**Version**: 1.0

For questions about this security policy, contact security@canopyiq.ai.