# Mock file system operations tool for testing
import base64
from typing import Dict, Any

SCHEMA = {
  "title": "File System Write",
  "description": "Write data to filesystem (mock implementation)",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": { "type": "string" },
      "bytes": { "type": "string", "description": "Base64 encoded data" }
    },
    "required": ["path", "bytes"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "bytes_written": { "type": "number" }
    },
    "required": ["success"]
  }
}

def write(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Mock filesystem write operation"""
    path = args["path"]
    data_b64 = args["bytes"]
    
    try:
        data = base64.b64decode(data_b64)
        bytes_written = len(data)
        
        # Mock: don't actually write to filesystem
        return {
            "success": True,
            "bytes_written": bytes_written,
            "path": path
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }