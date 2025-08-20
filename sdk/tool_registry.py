DEFAULT_SCHEMAS = {
  "email.send": {
    "type":"object",
    "properties": {
      "recipient": {"type":"string", "maxLength": 254},
      "subject": {"type":"string", "maxLength": 120},
      "body": {"type":"string", "maxLength": 10000}
    },
    "required": ["recipient","subject","body"],
    "additionalProperties": False
  },
  "crm.update": {
    "type":"object",
    "properties": {
      "id": {"type":"string"},
      "fields": {"type":"object"}
    },
    "required": ["id","fields"],
    "additionalProperties": False
  },
  "crm.read": {
    "type":"object",
    "properties": {"account_id":{"type":"string"}},
    "required": ["account_id"],
    "additionalProperties": False
  }
}