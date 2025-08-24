# Audit log writer
import json
import hashlib
from typing import Dict, Any, Optional

def write_log(entry: Dict[str, Any], prev_hash: Optional[bytes] = None) -> None:
    """Write an audit log entry (simplified implementation)"""
    # In production, this would write to Postgres with hash chain
    print(f"[AUDIT] {json.dumps(entry, default=str)}")
    
def compute_hash(entry: Dict[str, Any], prev_hash: Optional[bytes] = None) -> bytes:
    """Compute hash for audit entry"""
    entry_str = json.dumps(entry, sort_keys=True, default=str)
    if prev_hash:
        return hashlib.sha256(prev_hash + entry_str.encode()).digest()
    return hashlib.sha256(entry_str.encode()).digest()