# Troubleshooting

**Policy not applying?**  
- Check `canopyiq apply-policy` output for parse errors.
- Ensure agent SDK points to the correct policy set.

**Slack approvals not arriving?**
- Verify `SLACK_WEBHOOK_URL` and signing secret.
- Check inbound network rules and Slack app permissions.

**High latency?**
- Inspect `/metrics` p95.
- Ensure CPU/Memory limits are adequate and HPA is enabled.