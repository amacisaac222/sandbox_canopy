import redis, json
from typing import List
from ..settings import settings

r = redis.from_url(settings.REDIS_URL, decode_responses=True)

def _key(tenant:str, subject:str) -> str:
    return f"rbac:{tenant}:{subject}"

def set_roles(tenant:str, subject:str, roles:List[str]):
    r.set(_key(tenant,subject), json.dumps(sorted(set(roles))))

def get_roles(tenant:str, subject:str) -> List[str]:
    v = r.get(_key(tenant,subject))
    return json.loads(v) if v else []

def add_role(tenant:str, subject:str, role:str):
    roles = get_roles(tenant, subject)
    if role not in roles:
        roles.append(role)
        set_roles(tenant, subject, roles)