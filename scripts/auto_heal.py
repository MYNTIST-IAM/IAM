import os
import json
import yaml
from pathlib import Path
from datetime import datetime, timedelta

LEDGER_PATH = Path("security/token-ledger.yml")
REPORT_JSON = Path("reports/token_health.json")
POLICY_PATH = Path("security/autoheal-policy.yml")
OPS_ROOT = Path("ops/autoheal")


def load_yaml(path: Path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def save_yaml(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def parse_iso8601(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return datetime.min


def is_candidate(token: dict, policy: dict, scores: list) -> tuple[bool, str]:
    acceptance = policy.get("acceptance", {})
    last_n = acceptance.get("last_n", 7)
    min_critical = acceptance.get("min_critical_count_in_last_n", 3)
    max_drop_24h = acceptance.get("max_drop_24h", 0.4)
    min_days_since_last_used = acceptance.get("min_days_since_last_used", 14)

    # recent scores
    recent = scores[-last_n:] if scores else []
    critical_threshold = policy.get("risk", {}).get("critical_threshold", 0.2)
    critical_count = sum(1 for s in recent if s < critical_threshold)

    reasons = []
    if critical_count >= min_critical:
        reasons.append(f"critical_count={critical_count} in last {last_n}")

    # drop in 24h
    if len(recent) >= 2:
        drop = recent[-2] - recent[-1]
        if drop >= max_drop_24h:
            reasons.append(f"drop_24h={round(drop,3)}")

    # last used
    last_used_str = token.get("last_used")
    if last_used_str:
        delta_days = (datetime.now() - parse_iso8601(last_used_str)).days
        if delta_days >= min_days_since_last_used:
            reasons.append(f"unused_days={delta_days}")

    # exemptions
    ex_users = set(policy.get("exemptions", {}).get("users", []))
    ex_tokens = set(policy.get("exemptions", {}).get("tokens", []))
    if token.get("owner") in ex_users or str(token.get("token_id")) in ex_tokens:
        return False, "exempted"

    if reasons:
        return True, "; ".join(reasons)
    return False, ""


def propose_action(token: dict, policy: dict) -> dict:
    entity = token.get("entity_type", "service_account")
    role = token.get("role", "member")

    actions_cfg = policy.get("actions", {})
    if entity == "user":
        user_cfg = actions_cfg.get("user", {})
        role_cfg = user_cfg.get(role, user_cfg.get("member", {}))
        action_type = role_cfg.get("primary", "revoke_org_access")
        manifest = {"type": action_type}
        if action_type == "org_role_change":
            manifest["target_role"] = role_cfg.get("target_role", "member")
        return manifest
    else:
        sa_cfg = actions_cfg.get("service_account", {}).get("default", {})
        action_type = sa_cfg.get("primary", "scope_reduction")
        manifest = {"type": action_type}
        if action_type == "scope_reduction":
            manifest["target_scopes"] = sa_cfg.get("target_scopes", ["read:org", "repo"])
        return manifest


def build_manifest(token: dict, reason: str, policy: dict) -> dict:
    return {
        "token_id": token["token_id"],
        "owner": token.get("owner"),
        "entity_type": token.get("entity_type"),
        "current_state": {
            "role": token.get("role"),
            "state": token.get("state"),
            "scope": token.get("scope"),
        },
        "proposed_action": propose_action(token, policy),
        "reason": reason,
        "proposed_at": datetime.now().isoformat(),
    }


def update_ledger_with_proposal(ledger: dict, token_id: str, manifest: dict, pr_number: int | None):
    for t in ledger.get("tokens", []):
        if str(t.get("token_id")) == str(token_id):
            t["pending_action"] = {
                "type": manifest["proposed_action"]["type"],
                "reason": manifest["reason"],
                "evidence": {
                    "score_history_tail": t.get("score_history", [])[-7:],
                },
                "pr_number": pr_number,
                "proposed_at": manifest["proposed_at"],
            }
            audit_entry = {
                "event": "proposed",
                "action": manifest["proposed_action"],
                "reason": manifest["reason"],
                "before": {
                    "role": t.get("role"),
                    "state": t.get("state"),
                    "scope": t.get("scope"),
                },
                "pr_number": pr_number,
                "proposed_by": "auto-heal-bot",
                "timestamp": datetime.now().isoformat(),
            }
            trail = t.get("audit_trail", [])
            if not isinstance(trail, list):
                trail = []
            trail.append(audit_entry)
            t["audit_trail"] = trail
            return


def main():
    if not REPORT_JSON.exists():
        print("❌ No report found. Run survivability_scoring.py first.")
        return

    policy = load_yaml(POLICY_PATH)
    ledger = load_yaml(LEDGER_PATH)
    with open(REPORT_JSON, "r") as f:
        report = json.load(f)

    # index scores
    token_id_to_scores = {r["token_id"]: [h["score"] for h in r.get("score_history", [])] for r in report}

    candidates = []
    for token in ledger.get("tokens", []):
        scores = token_id_to_scores.get(token.get("token_id"), [])
        ok, reason = is_candidate(token, policy, scores)
        if ok:
            candidates.append((token, reason))

    if not candidates:
        print("✅ No auto-heal candidates found.")
        return

    date_dir = datetime.now().strftime("%Y%m%d")
    ops_dir = OPS_ROOT / date_dir
    ops_dir.mkdir(parents=True, exist_ok=True)

    manifests = []
    for token, reason in candidates:
        manifest = build_manifest(token, reason, policy)
        manifest_path = ops_dir / f"{token['token_id']}.yml"
        save_yaml(manifest_path, manifest)
        manifests.append((token, manifest_path, manifest))

    # Update ledger with proposals (PR number unknown yet; set to None)
    for token, manifest_path, manifest in manifests:
        update_ledger_with_proposal(ledger, token["token_id"], manifest, pr_number=None)

    save_yaml(LEDGER_PATH, ledger)

    # PR creation is intentionally left to workflow/git context; output manifest list for the CI step
    summary = {
        "manifests": [str(p) for _, p, _ in manifests],
        "count": len(manifests),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()


