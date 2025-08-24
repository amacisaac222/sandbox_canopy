# SDK (Python)

```python
from canopyiq import Guard

guard = Guard(policies="policies/baseline.yaml")

# Before performing an action:
decision = guard.check(
    action="http_request",
    attrs={"url": "https://api.external.com/upload", "bytes": 120_000}
)

if decision.allow:
    do_request()
elif decision.approval_required:
    await guard.request_approval(decision)
else:
    print("Blocked:", decision.reason)
```

- Async + sync APIs
- Built-in schema validation helpers