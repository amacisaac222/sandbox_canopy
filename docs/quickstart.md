# Quick Start

Get CanopyIQ running in minutes.

## 1) Install

```bash
git clone https://github.com/your-org/canopyiq.git
cd canopyiq
pip install -r requirements.txt
```

## 2) Run a demo agent

```bash
python examples/agent_demo.py
```

**Expected:**

1. The agent attempts an HTTP call.
2. CanopyIQ intercepts with policy.
3. You see ALLOW/DENY/APPROVAL decisions and an audit record.

## 3) Next steps

- Add the SDK to your agent → [SDK (Python)](reference/sdk-python.md)
- Write your first rules → [Policy Spec](reference/policy-spec.md)
- Send approvals to Slack → [Slack Approvals](tutorials/slack-approvals.md)