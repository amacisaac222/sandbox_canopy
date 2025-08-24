# Tutorial: HIPAA Baseline Policy

Start from a strict default and relax as needed.

```yaml
- name: "Block external PHI egress"
  match: "http_request"
  where:
    path_contains_any: ["patient", "ssn", "dob"]
  action: "deny"

- name: "Approve before emailing attachments"
  match: "send_email"
  where:
    has_attachment: true
  action: "approval"
```

**Deploy:**
```bash
canopyiq apply-policy policies/hipaa.yaml
```