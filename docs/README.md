# CanopyIQ Documentation

This directory contains the complete documentation for CanopyIQ built with MkDocs Material.

## Quick Start

### Prerequisites
```bash
pip install mkdocs mkdocs-material pymdown-extensions
```

### Development
```bash
# Serve locally with live reload
mkdocs serve

# Open http://127.0.0.1:8000
```

### Build & Deploy
```bash
# Build static site
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy --force
```

## Structure

- **Core Concepts**: Sandbox, Policy Engine, Audit Logging, Approvals, Compliance
- **Tutorials**: Hands-on guides for common scenarios
- **Reference**: CLI, SDKs, API, Policy Specification
- **Architecture**: System design and scaling guidance
- **Deployment**: Docker, Kubernetes, Terraform guides
- **Security**: Threat model and compliance details
- **Observability**: Metrics and logging integration

## Customization

- Brand colors are defined in `styles/brand.css`
- Logo and favicon are in `images/`
- All content uses Markdown with Material extensions
- Mermaid diagrams are supported for architecture diagrams

## Features

- ✅ Material Design theme with CanopyIQ branding
- ✅ Interactive navigation with search
- ✅ Code syntax highlighting
- ✅ Mermaid diagram support
- ✅ Mobile-responsive design
- ✅ Dark/light mode toggle
- ✅ Social links and GitHub integration