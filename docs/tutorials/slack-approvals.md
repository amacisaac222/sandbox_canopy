# Tutorial: Slack Approvals

Route approvals to Slack using an incoming webhook and interactive actions.

## Configure
- `SLACK_WEBHOOK_URL`
- `SLACK_SIGNING_SECRET`

## Test
```bash
curl -X POST http://localhost:8080/api/approvals/test
```

You should see a Slack message with **Approve** / **Deny** buttons. Click → decision updates + audit record created.