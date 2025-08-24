# Security & Compliance

## Signed Policy Bundles

Policies can be signed (Ed25519) and verified at startup for tamper-evident governance.

### Generate Keys

```bash
python cli/policy_sign.py gen-key --out-dir keys/
```

This creates:
- `keys/canopyiq_policy_private.key` - Private signing key (keep secure!)
- `keys/canopyiq_policy_public.key` - Public verification key

### Sign Policy Bundle

```bash
python cli/policy_sign.py sign app/policies/bundle.yaml --private-key keys/canopyiq_policy_private.key
```

Creates `app/policies/bundle.yaml.sig` with signature metadata:

```json
{
  "alg": "Ed25519",
  "created": "2025-08-23T12:34:56Z",
  "sha256": "<base64-hash>",
  "sig": "<base64-signature>",
  "pubkey_fingerprint": "canopyiq:v1:<8-hex>"
}
```

### Verify Policy Bundle

Local verification:
```bash
python cli/policy_sign.py verify app/policies/bundle.yaml \
  --public-key keys/canopyiq_policy_public.key \
  --signature app/policies/bundle.yaml.sig
```

### Server Verification

Configure the server to verify policy signatures at startup:

```bash
export POLICY_PUBLIC_KEY_B64=$(cat keys/canopyiq_policy_public.key)
export POLICY_SIG_PATH=app/policies/samples.yaml.sig
export POLICY_REQUIRE_SIGNATURE=true
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

- `POLICY_REQUIRE_SIGNATURE=true` - Server fails to start if signature is invalid
- `POLICY_REQUIRE_SIGNATURE=false` - Server logs warning but continues

## Kubernetes Deployment

Mount policy signature via Secret:

```bash
kubectl create secret generic canopyiq-policy-sig \
  --from-file=policy.sig=app/policies/samples.yaml.sig
```

Update Helm values:
```yaml
env:
  POLICY_PUBLIC_KEY_B64: "base64-encoded-public-key"
  POLICY_SIG_PATH: "/etc/canopyiq/policy.sig"
  POLICY_REQUIRE_SIGNATURE: "true"
```

## Benefits

1. **Tamper Detection**: Any modification to policies invalidates signature
2. **Audit Trail**: Signature metadata includes timestamp and key fingerprint  
3. **Compliance**: Cryptographic proof of policy integrity for auditors
4. **Zero Trust**: Server only trusts signed policies from authorized signers

## Key Management

- Store private keys in secure key management systems (AWS KMS, HashiCorp Vault)
- Rotate signing keys periodically
- Use different keys for different environments (dev/staging/prod)
- Include key fingerprints in audit logs for traceability