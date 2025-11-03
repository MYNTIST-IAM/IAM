import os
import json
import yaml
from pathlib import Path
from datetime import datetime, timedelta

LEDGER_PATH = Path("security/token-ledger.yml")
AGENT_LEDGER_PATH = Path("agents/agent-ledger.yml")
AGENT_REPORT_JSON = Path("reports/agent_health.json")
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
    """
    Simplified score-based candidate detection.
    - Score >= 0.5: No action (not a candidate)
    - Score >= 0.2 and < 0.5: Candidate (downgrade admin/owner to member)
    - Score < 0.2: Candidate (revoke org access)
    """
    # Get risk thresholds from policy
    risk = policy.get("risk", {})
    critical_threshold = risk.get("critical_threshold", 0.2)
    warning_threshold = risk.get("warning_threshold", 0.5)

    # Get current score
    current_score = token.get("survivability_score", 1.0)
    if not isinstance(current_score, (int, float)):
        current_score = 1.0

    # exemptions
    ex_users = set(policy.get("exemptions", {}).get("users", []))
    ex_tokens = set(policy.get("exemptions", {}).get("tokens", []))
    if token.get("owner") in ex_users or str(token.get("token_id")) in ex_tokens:
        return False, "exempted"

    # Score >= 0.5: No action needed
    if current_score >= warning_threshold:
        return False, f"score_above_threshold={round(current_score,3)}>=0.5"

    # Score < 0.2: Critical - revoke access
    if current_score < critical_threshold:
        return True, f"score={round(current_score,3)}<0.2"

    # Score >= 0.2 and < 0.5: Warning - downgrade admin/owner to member, or reduce scope for members
    if current_score >= critical_threshold and current_score < warning_threshold:
        role = token.get("role", "member")
        # Flag if role is admin/owner (downgrade to member) OR if already member (reduce scope)
        if role in ["admin", "owner"]:
            return True, f"score={round(current_score,3)}<0.5; role={role}"
        else:
            # Already member, but score is low - reduce scope (scope_reduction)
            return True, f"score={round(current_score,3)}<0.5; role={role} (scope_reduction)"

    return False, ""


def propose_action(token: dict, policy: dict) -> dict:
    """
    Propose action based on score:
    - Score < 0.2: revoke_org_access
    - Score >= 0.2 and < 0.5: if admin/owner, change to member
    """
    entity = token.get("entity_type", "service_account")
    role = token.get("role", "member")
    
    # Get current score
    current_score = token.get("survivability_score", 1.0)
    if not isinstance(current_score, (int, float)):
        current_score = 1.0
    
    # Get thresholds
    risk = policy.get("risk", {})
    critical_threshold = risk.get("critical_threshold", 0.2)
    warning_threshold = risk.get("warning_threshold", 0.5)
    
    if entity == "user":
        # Score < 0.2: Always revoke access
        if current_score < critical_threshold:
            return {"type": "revoke_org_access"}
        
        # Score >= 0.2 and < 0.5: 
        # - If admin/owner: downgrade to member
        # - If already member: reduce scope (scope_reduction)
        if current_score >= critical_threshold and current_score < warning_threshold:
            if role in ["admin", "owner"]:
                return {"type": "org_role_change", "target_role": "member"}
            else:
                # Already member, but score is low - reduce scope instead of revoke
                sa_cfg = policy.get("actions", {}).get("service_account", {}).get("default", {})
                target_scopes = sa_cfg.get("target_scopes", ["read:org", "repo"])
                return {"type": "scope_reduction", "target_scopes": target_scopes}
        
        # Score >= 0.5: Should not reach here (filtered by is_candidate)
        # Fallback to policy default
        actions_cfg = policy.get("actions", {})
        user_cfg = actions_cfg.get("user", {})
        role_cfg = user_cfg.get(role, user_cfg.get("member", {}))
        action_type = role_cfg.get("primary", "revoke_org_access")
        manifest = {"type": action_type}
        if action_type == "org_role_change":
            manifest["target_role"] = role_cfg.get("target_role", "member")
        return manifest
    else:
        # Service account: use scope reduction
        sa_cfg = policy.get("actions", {}).get("service_account", {}).get("default", {})
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
        # Extract repo names from repository_access
        repo_access = token.get("repository_access", [])
        if repo_access:
            # Get org name from audit_trail
            org_name = "MYNTIST-IAM"  # Default
            audit_trail = token.get("audit_trail", [])
            for entry in audit_trail:
                if isinstance(entry, str) and entry.startswith("org:"):
                    org_name = entry.split(":")[1]
                    break
            
            # Format repos as "org/repo"
            repos = [f"{org_name}/{repo['name']}" for repo in repo_access if isinstance(repo, dict) and 'name' in repo]
            if repos:
                manifest["targets"] = {"repos": repos}
    
    return manifest


# Note: We no longer add "proposed" events to the ledger
# Only "applied" events are added by apply_autoheal.py after successful application


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

    # Note: We no longer update the ledger with "proposed" events
    # Only "applied" events are added by apply_autoheal.py after successful application
    # Clean up any existing pending_action or proposed events from previous runs
    for token in ledger.get("tokens", []):
        if "pending_action" in token:
            del token["pending_action"]
        # Remove any "proposed" events from audit_trail
        audit_trail = token.get("audit_trail", [])
        if isinstance(audit_trail, list):
            # Keep only non-dict entries (org:, role:) and applied events
            cleaned_trail = [
                entry for entry in audit_trail 
                if not isinstance(entry, dict) or entry.get("event") != "proposed"
            ]
            token["audit_trail"] = cleaned_trail

    save_yaml(LEDGER_PATH, ledger)

    # PR creation is intentionally left to workflow/git context; output manifest list for the CI step
    summary = {
        "manifests": [str(p) for _, p, _ in manifests],
        "count": len(manifests),
    }
    
    # ===== AGENT AUTO-HEAL DETECTION (COMMENTED OUT - ENABLE WHEN READY) =====
    # 
    # Agent auto-heal detection is currently disabled. To enable:
    # 1. Uncomment the code below
    # 2. Ensure agent health reports are generated by survivability_scoring.py
    # 3. Update the policy to include agent-specific rules if needed
    #
    # # Load agent ledger and health report
    # if AGENT_REPORT_JSON.exists():
    #     with open(AGENT_REPORT_JSON, "r") as f:
    #         agent_report = json.load(f)
    #     
    #     agent_ledger = load_yaml(AGENT_LEDGER_PATH)
    #     if not agent_ledger:
    #         agent_ledger = {"agents": []}
    #     
    #     # Index agent scores
    #     agent_id_to_scores = {
    #         r["agent_id"]: [h["score"] for h in r.get("score_history", [])]
    #         for r in agent_report
    #     }
    #     
    #     agent_candidates = []
    #     for agent in agent_ledger.get("agents", []):
    #         agent_id = agent.get("agent_id")
    #         scores = agent_id_to_scores.get(agent_id, [])
    #         
    #         # Use same candidate logic as tokens (can be customized for agents)
    #         ok, reason = is_candidate(agent, policy, scores)
    #         if ok:
    #             # Link remediation to associated token
    #             associated_token_id = agent.get("associated_token_id")
    #             agent_candidates.append((agent, reason, associated_token_id))
    #     
    #     # Create manifests for agent candidates (link to token remediation)
    #     for agent, reason, token_id in agent_candidates:
    #         # Create manifest that references the agent and its associated token
    #         agent_manifest = {
    #             "agent_id": agent.get("agent_id"),
    #             "agent_name": agent.get("agent_name"),
    #             "associated_token_id": token_id,
    #             "current_state": {
    #                 "interaction_scope": agent.get("interaction_scope"),
    #                 "survivability_score": agent.get("survivability_score"),
    #                 "state": agent.get("state"),
    #             },
    #             "proposed_action": {
    #                 "type": "agent_scope_reduction",  # Or appropriate action for agents
    #                 "target_scopes": ["read:repo"],  # Reduced scope for agent
    #             },
    #             "reason": f"agent: {reason}",
    #             "proposed_at": datetime.now().isoformat(),
    #         }
    #         
    #         # Save agent manifest (optionally in same ops directory or separate)
    #         manifest_path = ops_dir / f"agent_{agent['agent_id']}.yml"
    #         save_yaml(manifest_path, agent_manifest)
    #         manifests.append((agent, manifest_path, agent_manifest))
    #     
    #     if agent_candidates:
    #         summary["agent_count"] = len(agent_candidates)
    #         summary["count"] = len(manifests)
    
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()


