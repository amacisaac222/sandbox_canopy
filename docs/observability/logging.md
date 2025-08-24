# Logging & SIEM

- JSON structured logs with request_id
- Sinks: stdout, file, Splunk HEC, Elastic
- Export audits:
  ```bash
  canopyiq export-audit --from 2025-08-01 --to 2025-08-31 --format json > audit.json
  ```