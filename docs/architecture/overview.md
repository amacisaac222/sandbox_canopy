# Architecture Overview

- **Control plane**: policy service, approvals service, audit log, metrics
- **Data plane**: per-agent sandbox + lightweight decision SDK
- **Stateless**: horizontal scale
- **Storage**: Postgres (audit), S3/Blob (exports), optional Redis (queues)

```mermaid
flowchart TB
  subgraph Agent Host
    AG[Agent]
    SD[CanopyIQ SDK]
  end
  subgraph Cluster
    CP[Policy Service]
    AP[Approvals Service]
    AU[(Audit DB)]
    ME[(Metrics)]
  end
  AG --> SD --> CP -->|allow/deny/approval| AG
  CP --> AU
  AP --> AU
```