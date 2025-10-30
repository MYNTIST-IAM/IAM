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

    # Get risk thresholds from policy
    risk = policy.get("risk", {})
    critical_threshold = risk.get("critical_threshold", 0.2)
    warning_threshold = risk.get("warning_threshold", 0.5)
    recovery_threshold = risk.get("recovery_threshold", 0.8)

    # Get current score
    current_score = token.get("survivability_score", 1.0)
    if not isinstance(current_score, (int, float)):
        current_score = 1.0

    # recent scores
    recent = scores[-last_n:] if scores else []
    
    # If score is above recovery threshold (0.8), skip unless there's a severe drop
    # Don't flag healthy tokens (score >= 0.8) just for being unused
    if current_score >= recovery_threshold:
        # Only check for severe drops (> 0.5) in healthy tokens
        if len(recent) >= 2:
            drop = recent[-2] - recent[-1]
            if drop >= 0.5:  # Severe drop from healthy state
                return True, f"severe_drop_from_healthy={round(drop,3)}"
        # Skip healthy tokens for other checks
        return False, "score_above_recovery_threshold"

    reasons = []
    
    # Score-based checks - only flag if score is below thresholds
    if current_score < critical_threshold:
        # Score < 0.2 - Critical - flag for any reason
        critical_count = sum(1 for s in recent if s < critical_threshold)
        if critical_count >= min_critical:
            reasons.append(f"score={round(current_score,3)}<0.2; critical_count={critical_count}/{last_n}")
        
        # Check for drops even in critical
        if len(recent) >= 2:
            drop = recent[-2] - recent[-1]
            if drop >= max_drop_24h:
                reasons.append(f"score={round(current_score,3)}<0.2; drop_24h={round(drop,3)}")
        
        # Check unused days for critical tokens
        last_used_str = token.get("last_used")
        if last_used_str:
            delta_days = (datetime.now() - parse_iso8601(last_used_str)).days
            if delta_days >= min_days_since_last_used:
                reasons.append(f"score={round(current_score,3)}<0.2; unused_days={delta_days}")
    
    elif current_score < warning_threshold:
        # Score 0.2-0.5 - Warning - flag for multiple issues
        critical_count = sum(1 for s in recent if s < critical_threshold)
        if critical_count >= min_critical:
            reasons.append(f"score={round(current_score,3)}<0.5; critical_count={critical_count}/{last_n}")
        
        # Check for significant drops
        if len(recent) >= 2:
            drop = recent[-2] - recent[-1]
            if drop >= max_drop_24h:
                reasons.append(f"score={round(current_score,3)}<0.5; drop_24h={round(drop,3)}")
        
        # Only flag unused if score is low AND unused (combined condition)
        last_used_str = token.get("last_used")
        if last_used_str:
            delta_days = (datetime.now() - parse_iso8601(last_used_str)).days
            # For warning scores, require longer unused period (double the threshold)
            if delta_days >= (min_days_since_last_used * 2):
                reasons.append(f"score={round(current_score,3)}<0.5; unused_days={delta_days}")
    
    # Score 0.5-0.8 - Degrading but not critical - only flag for severe issues
    elif current_score < recovery_threshold:
        # Only flag if multiple severe issues
        critical_count = sum(1 for s in recent if s < critical_threshold)
        severe_drop_threshold = max_drop_24h * 1.5  # More severe drop required
        
        if len(recent) >= 2:
            drop = recent[-2] - recent[-1]
            if drop >= severe_drop_threshold:
                reasons.append(f"degrading_score={round(current_score,3)}; severe_drop={round(drop,3)}")
        
        # Require multiple critical scores to flag degrading tokens
        if critical_count >= (min_critical + 2):  # At least 5 out of 7
            reasons.append(f"degrading_score={round(current_score,3)}; high_critical_count={critical_count}")

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
    manifest = {
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
    
    # For scope_reduction, include target repos if available in token metadata
    if manifest["proposed_action"].get("type") == "scope_reduction":
        repos = token.get("repos", [])
        if repos:
            manifest["targets"] = {"repos": repos}
    
    return manifest


def update_ledger_with_audit(ledger: dict, token_id: str, manifest: dict, pr_number: int | None):
    """Update ledger with audit trail only - pending_action should NOT be in ledger"""
    for t in ledger.get("tokens", []):
        if str(t.get("token_id")) == str(token_id):
            # Only add to audit trail, NOT pending_action
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
        # Output JSON for workflow compatibility
        print(json.dumps({
            "manifests": [],
            "count": 0,
            "error": "No report found. Ensure survivability_scoring.py runs before auto-heal detection."
        }, indent=2))
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
        print(json.dumps({
            "manifests": [],
            "count": 0,
            "message": "No auto-heal candidates found."
        }, indent=2))
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

    # Update ledger with audit trail only (pending_action stays in manifest files only)
    for token, manifest_path, manifest in manifests:
        update_ledger_with_audit(ledger, token["token_id"], manifest, pr_number=None)
    
    # Clean up any existing pending_action entries from previous runs
    # pending_action should only exist in manifest files, not in ledger
    for token in ledger.get("tokens", []):
        if "pending_action" in token:
            del token["pending_action"]

    save_yaml(LEDGER_PATH, ledger)

    # PR creation is intentionally left to workflow/git context; output manifest list for the CI step
    summary = {
        "manifests": [str(p) for _, p, _ in manifests],
        "count": len(manifests),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()


