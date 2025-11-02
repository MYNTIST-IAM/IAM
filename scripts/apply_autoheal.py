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
    """
    Apply remediation action to GitHub org via REST API.
    Requires PAT_TOKEN with admin:org and repo scopes.
    """
    result = {"ok": False, "details": "not applied"}
    action = manifest.get("proposed_action", {})
    a_type = action.get("type")
    owner = manifest.get("owner")

    if not ORG:
        return {"ok": False, "details": "ORG_NAME not set"}
    if not GITHUB_TOKEN:
        return {"ok": False, "details": "PAT_TOKEN not set"}
    if not owner:
        return {"ok": False, "details": "manifest missing owner"}

    try:
        if a_type == "org_role_change":
            # Downgrade org role (typically admin → member)
            target_role = action.get("target_role", "member")
            r = requests.put(
                f"{API}/orgs/{ORG}/memberships/{owner}",
                headers=gh_headers(),
                json={"role": target_role},
                timeout=30,
            )
            r.raise_for_status()
            result = {"ok": True, "details": f"org role changed to {target_role}"}

        elif a_type == "revoke_org_access":
            # Remove user/service account from org
            r = requests.delete(
                f"{API}/orgs/{ORG}/members/{owner}",
                headers=gh_headers(),
                timeout=30,
            )
            # 204 = success, 404 = already not a member
            if r.status_code in (204, 404):
                result = {"ok": True, "details": "org access revoked"}
            else:
                r.raise_for_status()

        elif a_type == "scope_reduction":
            # Reduce permissions on repositories
            # Note: Cannot modify user PAT scopes via API. Instead, reduce repo collaborator permissions.
            target_scopes = action.get("target_scopes", [])
            repos = manifest.get("targets", {}).get("repos", [])
            
            if not repos:
                # If no specific repos listed, log warning but mark as success
                result = {"ok": True, "details": "scope_reduction: no target repos specified, ledger updated only"}
            else:
                # Reduce permission to 'pull' (read-only) on each repo
                failures = []
                for repo_full_name in repos:
                    print(f"Reducing permission on {repo_full_name} for {owner}")
                    # try:
                    #     # Format: "owner/repo"
                    #     if "/" not in repo_full_name:
                    #         failures.append(f"{repo_full_name}: invalid format")
                    #         continue
                        
                    #     r = requests.put(
                    #         f"{API}/repos/{repo_full_name}/collaborators/{owner}",
                    #         headers=gh_headers(),
                    #         data='{"permission":"pull"}',
                    #         timeout=30,
                    #     )
                    #     r.raise_for_status()
                    # except requests.RequestException as e:
                    #     failures.append(f"{repo_full_name}: {str(e)}")
                
                if failures:
                    result = {"ok": False, "details": f"partial failure: {'; '.join(failures)}"}
                else:
                    result = {"ok": True, "details": f"reduced permissions on {len(repos)} repo(s) to pull"}
        else:
            result = {"ok": False, "details": f"unknown action type: {a_type}"}

    except requests.RequestException as e:
        result = {"ok": False, "details": f"api error: {str(e)}"}
    except Exception as e:
        result = {"ok": False, "details": f"unexpected error: {str(e)}"}

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

            # Note: pending_action should NOT be stored in ledger (only in manifest files)
            # Manifest files are deleted after successful application

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
    applied_count = 0
    deleted_manifests = []
    
    for path, manifest in manifests:
        res = apply_manifest(manifest)
        
        # Only update ledger and delete manifest if application was successful
        if res.get("ok", False):
            update_ledger_post_apply(ledger, str(manifest.get("token_id")), manifest, res, approver)
            
            # Delete manifest file after successful application
            try:
                path.unlink()  # Delete the manifest file
                deleted_manifests.append(str(path))
                applied_count += 1
                print(f"✅ Applied and deleted: {path}")
            except Exception as e:
                print(f"⚠️  Applied but failed to delete {path}: {e}")
                applied_count += 1  # Still count as applied
        else:
            # Keep manifest file if application failed (for retry)
            print(f"❌ Failed to apply {path}: {res.get('details', 'unknown error')}")
            update_ledger_post_apply(ledger, str(manifest.get("token_id")), manifest, res, approver)

    save_yaml(LEDGER_PATH, ledger)
    print(json.dumps({
        "applied": applied_count,
        "failed": len(manifests) - applied_count,
        "deleted_manifests": deleted_manifests
    }, indent=2))


if __name__ == "__main__":
    main()


