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

    # Update ledger with proposals (PR number unknown yet; set to None)
    for token, manifest_path, manifest in manifests:
        update_ledger_with_proposal(ledger, token["token_id"], manifest, pr_number=None)

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


