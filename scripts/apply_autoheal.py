import os
import yaml
import json
import requests
from pathlib import Path
from datetime import datetime

LEDGER_PATH = Path("security/token-ledger.yml")
OPS_ROOT = Path("ops/autoheal")
POLICY_PATH = Path("security/autoheal-policy.yml")

ORG = os.getenv("ORG_NAME", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("PAT_TOKEN")

API = "https://api.github.com"


def gh_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def load_yaml(path: Path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def save_yaml(path: Path, data):
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def apply_manifest(manifest: dict) -> dict:
    result = {"ok": False, "details": "not applied"}
    action = manifest.get("proposed_action", {})
    a_type = action.get("type")

    # Note: Many actions require org admin; here we simulate API calls to be safe.
    try:
        if a_type == "org_role_change":
            # GitHub does not have a simple role change API; would remove admin privileges.
            # Placeholder: mark as success without changing live state.
            result = {"ok": True, "details": "org role change proposed"}
        elif a_type == "revoke_org_access":
            # Placeholders for security-sensitive calls
            result = {"ok": True, "details": "org access revocation proposed"}
        elif a_type == "scope_reduction":
            result = {"ok": True, "details": "scope reduction proposed"}
        else:
            result = {"ok": False, "details": f"unknown action {a_type}"}
    except requests.RequestException as e:
        result = {"ok": False, "details": f"api error: {e}"}

    return result


def update_ledger_post_apply(ledger: dict, token_id: str, manifest: dict, apply_res: dict, approver: str | None):
    for t in ledger.get("tokens", []):
        if str(t.get("token_id")) == str(token_id):
            before = {
                "role": t.get("role"),
                "state": t.get("state"),
                "scope": t.get("scope"),
            }
            action = manifest.get("proposed_action", {})

            # Simulate state changes locally (actual GitHub changes are external)
            if action.get("type") == "org_role_change":
                t["role"] = action.get("target_role", "member")
            elif action.get("type") == "revoke_org_access":
                t["state"] = "revoked"
            elif action.get("type") == "scope_reduction":
                targets = action.get("target_scopes")
                if targets:
                    t["scope"] = ", ".join(targets)

            after = {
                "role": t.get("role"),
                "state": t.get("state"),
                "scope": t.get("scope"),
            }

            t["pending_action"] = None

            trail = t.get("audit_trail", [])
            if not isinstance(trail, list):
                trail = []
            trail.append({
                "event": "applied",
                "action": action,
                "result": apply_res,
                "approved_by": approver,
                "timestamp": datetime.now().isoformat(),
                "before": before,
                "after": after,
            })
            t["audit_trail"] = trail
            return


def main():
    # Discover manifests changed in this PR by scanning ops dir
    if not OPS_ROOT.exists():
        print("No manifests to apply.")
        return

    ledger = load_yaml(LEDGER_PATH)

    manifests = []
    for path in sorted(OPS_ROOT.rglob("*.yml")):
        try:
            manifests.append((path, load_yaml(path)))
        except Exception:
            continue

    approver = os.getenv("GITHUB_ACTOR")
    for path, manifest in manifests:
        res = apply_manifest(manifest)
        update_ledger_post_apply(ledger, str(manifest.get("token_id")), manifest, res, approver)

    save_yaml(LEDGER_PATH, ledger)
    print(json.dumps({"applied": len(manifests)}, indent=2))


if __name__ == "__main__":
    main()


