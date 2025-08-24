# Slack approval notifications
import requests
import json
from ..settings import settings

def request_approval(pending_id: str, summary: str) -> None:
    """Send approval request to Slack with interactive buttons"""
    if not settings.SLACK_WEBHOOK_URL:
        print(f"[WARN] No Slack webhook configured for approval: {summary}")
        return
    
    payload = {
        "text": f"🔒 Approval Required: {summary}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Approval Required*\n{summary}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Approve"
                        },
                        "style": "primary",
                        "action_id": "approve",
                        "value": pending_id
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "❌ Deny"
                        },
                        "style": "danger",
                        "action_id": "deny",
                        "value": pending_id
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Failed to send Slack approval request: {e}")