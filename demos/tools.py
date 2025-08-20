"""
Fake tools for demonstration purposes
"""

def crm_read(account_id: str) -> dict:
    """Simulate reading from CRM"""
    return {
        "account_id": account_id,
        "name": "Acme Corp",
        "status": "active",
        "revenue": 150000
    }

def email_send(recipient: str, subject: str, body: str) -> dict:
    """Simulate sending an email"""
    return {
        "status": "sent",
        "recipient": recipient,
        "subject": subject,
        "message_id": "msg_123456"
    }

def crm_update(id: str, fields: dict) -> dict:
    """Simulate updating CRM record"""
    return {
        "id": id,
        "updated_fields": fields,
        "status": "updated"
    }