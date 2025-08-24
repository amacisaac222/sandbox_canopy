# Tutorial: Run 100 Test Agents

Spin up 100 dummy agents to validate scale.

## Prereqs
- Docker or Kubernetes
- CanopyIQ runtime running

## Steps

1. **Launch runtime:**
   ```bash
   canopyiq start
   ```

2. **Apply policies:**
   ```bash
   canopyiq apply-policy policies/baseline.yaml
   ```

3. **Launch generator:**
   ```bash
   python scripts/agent_stress.py --agents 100 --rate 20/s
   ```

4. **Observe:**
   - `/metrics` p95 latency
   - Audit volumes and decisions