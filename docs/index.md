# Your Agents, Under Control

Enterprise AI is powerful—but risky. **CanopyIQ** is the safety layer that makes agents **safe by default** with sandboxing, policy enforcement, audit logging, and human approvals—scaling from 10 to 10,000+ agents.

!!! success "What you get"
    - **Sandbox every action** — contain agents at runtime
    - **Enforce policy** — real-time allow/deny/approve in <10ms
    - **Prove compliance** — immutable audits, export to SIEM
    - **Scale safely** — stateless, horizontally scalable

```mermaid
flowchart LR
    A[Agent] --> B[CanopyIQ Sandbox]
    B --> C{Policy Engine<br/>(< 10ms)}
    C -->|Allow| D[Action Executes]
    C -->|Deny| E[Blocked + Audit]
    C -->|Approval| F[Human-in-the-Loop]
    F -->|Approve/Deny| C
    E --> G[(Immutable Audit Log)]
    D --> G
```

**Quick links** → [Quick Start](quickstart.md) • [Policy Spec](reference/policy-spec.md) • [Security](security/security-compliance.md)