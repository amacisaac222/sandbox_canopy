"""
CanopyIQ Slack Integration Utilities
Handles webhook notifications and interactive components
"""
import os
import hmac
import hashlib
import httpx
import json
import time
from typing import Optional, Dict, Any
from fastapi import HTTPException

# Slack configuration
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "").encode()

async def send_slack_webhook(message: Dict[str, Any]) -> bool:
    """Send message to Slack via incoming webhook"""
    if not SLACK_WEBHOOK_URL:
        print("Warning: SLACK_WEBHOOK_URL not configured, skipping Slack notification")
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SLACK_WEBHOOK_URL,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"Failed to send Slack webhook: {e}")
        return False

def create_contact_notification(name: str, email: str, company: str, message: str, submission_id: int) -> Dict[str, Any]:
    """Create Slack message for new contact submission"""
    admin_url = f"{os.getenv('BASE_URL', 'http://localhost:8080')}/admin/contacts"
    
    return {
        "text": f"New contact submission from {name}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔔 New Contact Submission"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Name:* {name}"
                    },
                    {
                        "type": "mrkdwn", 
                        "text": f"*Email:* {email}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Company:* {company}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Submission ID:* #{submission_id}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Message:*\n{message[:500]}{'...' if len(message) > 500 else ''}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View in Admin"
                        },
                        "url": admin_url,
                        "style": "primary"
                    }
                ]
            }
        ]
    }

def create_approval_notification(approval_id: int, actor: str, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create Slack message for approval request with interactive buttons"""
    callback_url = f"{os.getenv('BASE_URL', 'http://localhost:8080')}/slack/interactive"
    
    # Format payload for display
    payload_text = ""
    if payload:
        for key, value in payload.items():
            payload_text += f"*{key.title()}:* {value}\n"
    
    return {
        "text": f"Approval requested by {actor}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚠️ Approval Required"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Requested by:* {actor}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Action:* {action}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Approval ID:* #{approval_id}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:* Pending"
                    }
                ]
            }
        ] + ([{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Details:*\n{payload_text}"
            }
        }] if payload_text else []) + [
            {
                "type": "actions",
                "block_id": f"approval_{approval_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Approve"
                        },
                        "style": "primary",
                        "value": f"approve_{approval_id}",
                        "action_id": "approve_action"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "❌ Deny"
                        },
                        "style": "danger", 
                        "value": f"deny_{approval_id}",
                        "action_id": "deny_action"
                    }
                ]
            }
        ]
    }

def verify_slack_signature(request_body: str, timestamp: str, signature: str) -> bool:
    """Verify Slack request signature for security"""
    if not SLACK_SIGNING_SECRET:
        print("Warning: SLACK_SIGNING_SECRET not configured, skipping signature verification")
        return True  # Allow in development
    
    # Check timestamp to prevent replay attacks
    current_time = int(time.time())
    request_time = int(timestamp)
    if abs(current_time - request_time) > 60 * 5:  # 5 minutes
        return False
    
    # Verify signature
    basestring = f"v0:{timestamp}:{request_body}"
    expected_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET,
        basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

def parse_slack_payload(form_data: Dict[str, str]) -> Dict[str, Any]:
    """Parse Slack interactive component payload"""
    try:
        payload = json.loads(form_data.get("payload", "{}"))
        return payload
    except (json.JSONDecodeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid Slack payload: {e}")

def extract_approval_action(payload: Dict[str, Any]) -> tuple[str, int]:
    """Extract action and approval ID from Slack button interaction"""
    try:
        actions = payload.get("actions", [])
        if not actions:
            raise ValueError("No actions found in payload")
        
        action = actions[0]
        value = action.get("value", "")
        
        # Parse value like "approve_123" or "deny_123"
        parts = value.split("_", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid action value format: {value}")
        
        action_type = parts[0]  # "approve" or "deny"
        approval_id = int(parts[1])
        
        return action_type, approval_id
        
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid approval action: {e}")

async def update_approval_message(response_url: str, approval_id: int, status: str, approved_by: str) -> bool:
    """Update the original Slack message with approval result"""
    try:
        status_emoji = "✅" if status == "approved" else "❌"
        status_color = "good" if status == "approved" else "danger"
        
        message = {
            "text": f"Approval #{approval_id} has been {status}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{status_emoji} Approval {status.title()}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Approval ID:* #{approval_id}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Status:* {status.title()}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*{status.title()} by:* {approved_by}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Time:* {time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        }
                    ]
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                response_url,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            response.raise_for_status()
            return True
            
    except Exception as e:
        print(f"Failed to update Slack message: {e}")
        return False