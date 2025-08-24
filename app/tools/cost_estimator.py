import json, os
from typing import Dict, Any

PRICES = {}
def _load_prices():
    global PRICES
    path = os.path.join(os.path.dirname(__file__), "data", "prices.json")
    with open(path, "r") as f:
        PRICES = json.load(f)
_load_prices()

SCHEMA = {
  "title": "Cloud Cost Estimator",
  "description": "Rough, static estimator for cloud ops; use before cloud.ops",
  "inputSchema": {
    "type": "object",
    "properties": {
      "provider": { "type": "string", "enum": ["aws","gcp","azure"] },
      "action":   { "type": "string" },
      "units":    { "type": "number", "minimum": 0 }
    },
    "required": ["provider","action","units"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "estimated_cost_usd": { "type": "number" },
      "unit": { "type": "string" },
      "usd_per_unit": { "type": "number" },
      "source": { "type": "string" }
    },
    "required": ["estimated_cost_usd"]
  }
}

def estimate(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    provider = args["provider"]
    action   = args["action"]
    units    = float(args["units"])
    ent = PRICES.get(provider, {}).get(action)
    if not ent:
        raise PermissionError(f"No price mapping for {provider}.{action}")
    est = float(ent["usd_per_unit"]) * units
    return {
        "estimated_cost_usd": round(est, 4),
        "unit": ent["unit"],
        "usd_per_unit": ent["usd_per_unit"],
        "source": "static-pricebook"
    }