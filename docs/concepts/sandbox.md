# Sandbox

Each agent runs inside an **isolated sandbox** (container or microVM). Isolation prevents a misbehaving agent from impacting hosts or other tenants.

**Key properties**
- Process, FS, and network isolation
- Ephemeral by default; optional persistence via volumes/snapshots
- Fast spin-up for parallel tasks

**When to use persistent state**
- Long-running coding agents
- Evaluations that must cache datasets
- Iterative workflows needing replay/snapshots