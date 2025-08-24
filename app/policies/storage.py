import os, base64, hashlib, json, datetime, shutil, psycopg2
from typing import Tuple
from .verify import verify_bundle

VERS_DIR = os.getenv("CANOPYIQ_POLICY_DIR","./app/policies/versions")

def _ensure_dir(): 
    os.makedirs(VERS_DIR, exist_ok=True)

def register_policy(db_url:str, policy_path:str, sig_path:str, public_key_b64:str) -> Tuple[str,str,str,bytes]:
    _ensure_dir()
    ok, msg = verify_bundle(policy_path, sig_path, public_key_b64)
    if not ok:
        raise RuntimeError(f"Signature invalid: {msg}")

    with open(policy_path,"rb") as f: 
        data = f.read()
    sha = hashlib.sha256(data).digest()
    short = hashlib.sha256(sha).hexdigest()[:4]
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    version = f"{ts}_{short}"

    # copy files into versions dir
    dst_yaml = os.path.join(VERS_DIR, f"{version}.yaml")
    dst_sig  = os.path.join(VERS_DIR, f"{version}.yaml.sig")
    shutil.copyfile(policy_path, dst_yaml)
    shutil.copyfile(sig_path, dst_sig)

    with psycopg2.connect(db_url) as cx, cx.cursor() as cur:
        cur.execute("INSERT INTO policy_version(version, sha256, path, sig_path) VALUES (%s,%s,%s,%s)",
                    (version, psycopg2.Binary(sha), dst_yaml, dst_sig))
        cx.commit()
    return version, dst_yaml, dst_sig, sha