from fnmatch import fnmatch
from jsonschema import validate, ValidationError

class Decision(str): pass  # "allow" | "deny" | "needs_approval"

def tool_allowed(tool_name: str, allow: list[str], deny: list[str]) -> bool:
    return any(fnmatch(tool_name, a) for a in allow) and not any(fnmatch(tool_name, d) for d in deny)

def domain_allowed(host: str, allow_domains: list[str], deny_all_others: bool) -> bool:
    if not deny_all_others: return True
    return any(host.endswith(d) for d in allow_domains)

def validate_params(schema: dict, params: dict) -> tuple[bool, str|None]:
    try:
        validate(instance=params, schema=schema)
        return True, None
    except ValidationError as e:
        return False, str(e)