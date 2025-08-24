# Cost Controls

CanopyIQ provides proactive cost controls for cloud operations through cost estimation and budget enforcement.

## Cost Estimator Tool

The `cloud.estimate` tool provides pre-flight cost predictions based on a static price book:

```json
{
  "tool": "cloud.estimate",
  "arguments": {
    "provider": "aws",
    "action": "ec2.run_instances", 
    "units": 10
  }
}
```

Returns:
```json
{
  "estimated_cost_usd": 0.92,
  "unit": "instance-hour",
  "usd_per_unit": 0.092,
  "source": "static-pricebook"
}
```

## Policy Integration

Policies can enforce cost thresholds and require estimates before expensive operations:

```yaml
- name: "Require cost estimate before cloud ops"
  match: "cloud.ops"
  where:
    estimated_cost_usd_over: 10
  action: approval
  reason: "High-cost action requires approval"
```

## Supported Providers & Actions

### AWS
- `ec2.run_instances`: $0.092/instance-hour
- `s3.put_object`: $0.005/1k-requests
- `bedrock.invocation`: $0.002/1k-tokens

### GCP
- `compute.instances.insert`: $0.085/instance-hour

### Azure
- `vm.create`: $0.09/instance-hour

## Cost Workflow

1. **Estimate**: Agent calls `cloud.estimate` before expensive operations
2. **Evaluate**: Policy engine checks estimated cost against thresholds
3. **Approve**: High-cost operations require human approval
4. **Execute**: `cloud.ops` proceeds with cost tracking
5. **Budget**: Per-tenant daily/weekly budget enforcement (future)

## Configuration

Price data is stored in `app/tools/data/prices.json` and can be updated with real-time pricing APIs.

For production deployments, consider integrating with:
- AWS Cost Explorer API
- GCP Cloud Billing API  
- Azure Cost Management API