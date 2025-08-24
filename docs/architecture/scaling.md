# Scaling to 10k+ Agents

- Stateless services with HPA (K8s)
- p95 < 10ms policy eval (in-memory rules + JIT filters)
- Batching and circuit-breakers for bursts
- Backpressure queues for approvals