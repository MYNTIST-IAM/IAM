import yaml
import math
import json
from pathlib import Path
from datetime import datetime

# --- Config paths ---
LEDGER_PATH = Path("security/token-ledger.yml")
AGENT_LEDGER_PATH = Path("agents/agent-ledger.yml")
REPORT_JSON = Path("reports/token_health.json")
REPORT_MD = Path("reports/token_health_report.md")
AGENT_REPORT_JSON = Path("reports/agent_health.json")
AGENT_REPORT_MD = Path("reports/agent_health_report.md")
HISTORY_JSON = Path("reports/score_history.json")
DASHBOARD_PUBLIC = Path("dashboard/public")
MAX_HISTORY_ENTRIES = 7  # Keep last 7 entries for weekly trend graph

# --- Utility functions ---
def calculate_score(scope, used, drift, audit, token_data=None):
    """Enhanced scoring: S = base_score * role_multiplier * repo_multiplier * time_factor * audit_factor"""
    
    # Base score calculation
    granted = len(scope.split(','))  # Calculate granted permissions based on scope
    if used == 0:
        used = 1  # avoid divide-by-zero
    Q_perms = granted / used
    base_score = (1 / Q_perms) * math.cos(drift)
    
    # Role multiplier (higher for admin users)
    role_multiplier = 1.0
    if token_data and token_data.get('entity_type') == 'user':
        role = token_data.get('role', 'member')
        if role == 'admin':
            role_multiplier = 2.0  # Significant boost for admin users
        elif role == 'member':
            role_multiplier = 1.5  # Good boost for members
    
    # Repository access multiplier
    repo_multiplier = 1.0
    if token_data and 'repo_access_summary' in token_data:
        repo_summary = token_data['repo_access_summary']
        total_repos = repo_summary.get('total_repos', 0)
        private_repos = repo_summary.get('private_repos', 0)
        admin_repos = repo_summary.get('admin_repos', 0)
        
        # Boost score based on repository access
        if total_repos > 0:
            repo_multiplier = 1.0 + (total_repos * 0.1)  # 0.1 per repo
            if private_repos > 0:
                repo_multiplier += (private_repos * 0.2)  # Extra boost for private repo access
            if admin_repos > 0:
                repo_multiplier += (admin_repos * 0.3)  # Extra boost for admin repo access
    
    # Time factor (penalize old tokens)
    time_factor = 1.0
    if token_data and 'issued_on' in token_data:
        try:
            from datetime import datetime
            issued_date = datetime.strptime(token_data['issued_on'], '%Y-%m-%d')
            days_old = (datetime.now() - issued_date).days
            
            if days_old > 100:  # Penalize tokens older than 100 days
                time_factor = max(0.3, 1.0 - (days_old - 100) * 0.01)  # Reduce by 1% per day after 100
            elif days_old < 30:  # Boost for recent tokens
                time_factor = 1.2
            elif token_data.get('entity_type') == 'user':  # Special boost for users
                time_factor = 1.1  # Slight boost for all users regardless of age
        except:
            time_factor = 1.0  # Default if date parsing fails
    
    # Audit factor (enhanced for users)
    audit_factor = 0.5  # Default for no audit
    if audit:
        audit_factor = 1.0
    elif token_data and token_data.get('entity_type') == 'user':
        # For users, give much better credit for having org/role info
        audit_trail = token_data.get('audit_trail', [])
        audit_factor = 0.9  # High base credit for users
        if any('org:' in str(item) for item in audit_trail):
            audit_factor = 1.0  # Full credit for org info
        if any('role:' in str(item) for item in audit_trail):
            audit_factor = 1.0  # Full credit for role info
    
    # Calculate final score
    S = base_score * role_multiplier * repo_multiplier * time_factor * audit_factor
    
    # Normalize score to 0-1 range
    # Cap the score at 1.0 (survivability scores should be 0-1)
    S = min(1.0, max(0.0, S))
    
    return round(S, 3)


def get_status(score):
    """Get status based on score thresholds"""
    if score >= 0.8:
        return "Healthy"
    elif score >= 0.2:
        return "Degrading"  # 0.2 to 0.8 is degrading/warning range
    else:
        return "Critical"  # < 0.2 is critical


def update_score_history(token_id, new_score, existing_history):
    """
    Update score history for a token, keeping max 7 entries.
    Returns updated history array.
    """
    if not existing_history or not isinstance(existing_history, list):
        existing_history = []
    
    # Add new score with timestamp
    new_entry = {
        "timestamp": datetime.now().isoformat(),
        "score": new_score
    }
    
    existing_history.append(new_entry)
    
    # Keep only last 7 entries
    if len(existing_history) > MAX_HISTORY_ENTRIES:
        existing_history = existing_history[-MAX_HISTORY_ENTRIES:]
    
    return existing_history


# --- Load YAML ---
with open(LEDGER_PATH, "r") as f:
    data = yaml.safe_load(f)

results = []
updated_tokens = []

# --- Calculate scores ---
for token in data["tokens"]:
    S = calculate_score(
        token["scope"],  # Pass scope directly
        token.get("used_permissions", 1),  # Use permissions defaults to 1 if missing
        token.get("scope_drift", 0.0),  # Scope drift defaults to 0.0 if missing
        bool(token.get("audit_trail", [])),  # Audit trail is used as a boolean indicator
        token  # Pass the entire token data for enhanced scoring
    )

    status = get_status(S)

    # Update score history (max 7 entries)
    score_history = update_score_history(
        token["token_id"],
        S,
        token.get("score_history", [])
    )

    # Update token with new score and history
    token["survivability_score"] = S
    token["score_history"] = score_history
    token["last_scored"] = datetime.now().isoformat()
    
    updated_tokens.append(token)

    # Prepare result data
    result_data = {
        "token_id": token["token_id"],
        "owner": token["owner"],
        "survivability_score": S,
        "status": status,
        "score_history": score_history
    }
    
    # Add repository access info if available
    if 'repo_access_summary' in token:
        result_data['repo_access'] = token['repo_access_summary']
    
    # Add role info if available
    if 'role' in token:
        result_data['role'] = token['role']
    
    results.append(result_data)


# --- Save updated ledger with scores ---
data["tokens"] = updated_tokens
with open(LEDGER_PATH, "w") as f:
    yaml.dump(data, f, default_flow_style=False, sort_keys=False)

print("✅ Updated token ledger with new scores")

# --- Write JSON report ---
REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
with open(REPORT_JSON, "w") as f:
    json.dump(results, f, indent=2)

# --- Write score history JSON (for graphing) ---
with open(HISTORY_JSON, "w") as f:
    json.dump(results, f, indent=2)

# --- Copy JSON files to dashboard/public for React app ---
if DASHBOARD_PUBLIC.exists():
    DASHBOARD_PUBLIC.mkdir(parents=True, exist_ok=True)
    # Copy token_health.json
    import shutil
    dashboard_health = DASHBOARD_PUBLIC / "token_health.json"
    shutil.copy2(REPORT_JSON, dashboard_health)
    # Copy score_history.json
    dashboard_history = DASHBOARD_PUBLIC / "score_history.json"
    shutil.copy2(HISTORY_JSON, dashboard_history)
    print("✅ Copied JSON files to dashboard/public/")

# --- Write Markdown report ---
with open(REPORT_MD, "w") as f:
    f.write("# Token Health Report\n\n")
    f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
    f.write("| Token ID | Owner | Role | Score | Status | Repos | Private | Admin | Trend (Last 7) |\n")
    f.write("|----------|-------|------|-------|--------|-------|---------|-------|----------------|\n")
    for r in results:
        history_scores = [h["score"] for h in r["score_history"]]
        trend = " → ".join([str(s) for s in history_scores])
        
        # Get role info
        role = r.get('role', 'N/A')
        
        # Get repo access info
        repo_info = r.get('repo_access', {})
        total_repos = repo_info.get('total_repos', 0)
        private_repos = repo_info.get('private_repos', 0)
        admin_repos = repo_info.get('admin_repos', 0)
        
        f.write(f"| {r['token_id']} | {r['owner']} | {role} | {r['survivability_score']} | {r['status']} | {total_repos} | {private_repos} | {admin_repos} | {trend} |\n")

print("✅ Survivability scoring complete. Reports generated in /reports/")
print(f"📊 Score history maintained (max {MAX_HISTORY_ENTRIES} entries per token)")

# --- Agent Scoring ---
# Load agent ledger and token ledger for reference
try:
    if AGENT_LEDGER_PATH.exists():
        with open(AGENT_LEDGER_PATH, "r") as f:
            agent_data = yaml.safe_load(f) or {"agents": []}
    else:
        agent_data = {"agents": []}
    
    # Create token lookup for agent scoring
    token_lookup = {str(t["token_id"]): t for t in updated_tokens}
    
    agent_results = []
    updated_agents = []
    
    # Calculate scores for agents
    for agent in agent_data.get("agents", []):
        agent_id = agent.get("agent_id")
        associated_token_id = str(agent.get("associated_token_id", ""))
        
        # Get associated token for context
        associated_token = token_lookup.get(associated_token_id)
        
        # Validate agent has associated token
        if not associated_token:
            print(f"⚠️  Warning: Agent {agent_id} has invalid associated_token_id: {associated_token_id}")
            # Skip scoring but keep agent
            updated_agents.append(agent)
            continue
        
        # Calculate agent score using interaction_scope
        interaction_scope = agent.get("interaction_scope", "read:repo")
        
        # Create agent_data dict for scoring function (merging agent and token context)
        agent_scoring_data = {
            **associated_token,  # Include token context
            "entity_type": "agent",  # Mark as agent
            "scope": interaction_scope,  # Use agent's interaction scope
        }
        
        S = calculate_score(
            interaction_scope,  # Use agent's interaction_scope
            agent.get("used_permissions", 1),  # Default to 1 if missing
            agent.get("scope_drift", 0.0),  # Default to 0.0 if missing
            bool(agent.get("audit_trail", [])),  # Audit trail indicator
            agent_scoring_data  # Pass merged data for context
        )
        
        status = get_status(S)
        
        # Update agent score history (max 7 entries)
        score_history = update_score_history(
            agent_id,
            S,
            agent.get("score_history", [])
        )
        
        # Update agent with new score and history
        agent["survivability_score"] = S
        agent["score_history"] = score_history
        agent["last_scored"] = datetime.now().isoformat()
        
        updated_agents.append(agent)
        
        # Prepare result data
        result_data = {
            "agent_id": agent_id,
            "agent_name": agent.get("agent_name"),
            "associated_token_id": associated_token_id,
            "survivability_score": S,
            "status": status,
            "score_history": score_history,
            "purpose": agent.get("purpose"),
            "interaction_scope": interaction_scope
        }
        
        agent_results.append(result_data)
    
    # Save updated agent ledger
    agent_data["agents"] = updated_agents
    if updated_agents:
        with open(AGENT_LEDGER_PATH, "w") as f:
            yaml.dump(agent_data, f, default_flow_style=False, sort_keys=False)
        print(f"✅ Updated agent ledger with new scores ({len(updated_agents)} agents)")
    
    # Write agent health JSON report
    if agent_results:
        AGENT_REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
        with open(AGENT_REPORT_JSON, "w") as f:
            json.dump(agent_results, f, indent=2)
        
        # Write agent health Markdown report
        with open(AGENT_REPORT_MD, "w") as f:
            f.write("# Agent Health Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
            f.write("| Agent ID | Agent Name | Associated Token | Score | Status | Scope | Trend (Last 7) |\n")
            f.write("|----------|------------|------------------|-------|--------|-------|----------------|\n")
            for r in agent_results:
                history_scores = [h["score"] for h in r["score_history"]]
                trend = " → ".join([str(s) for s in history_scores])
                f.write(f"| {r['agent_id']} | {r['agent_name']} | {r['associated_token_id']} | {r['survivability_score']} | {r['status']} | {r['interaction_scope']} | {trend} |\n")
        
        print(f"✅ Agent health reports generated ({len(agent_results)} agents)")
    else:
        print("ℹ️  No agents found to score")

except Exception as e:
    print(f"⚠️  Error processing agents: {e}")
    import traceback
    traceback.print_exc()

# --- Product Health Calculation ---
# Calculate aggregate health for products after token/agent scoring
try:
    # Import calculate_product_health module
    import importlib.util
    calculate_health_path = Path(__file__).parent / "calculate_product_health.py"
    
    if calculate_health_path.exists():
        spec = importlib.util.spec_from_file_location("calculate_product_health", calculate_health_path)
        calc_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(calc_module)
        
        # Call the calculate_product_health function
        calc_module.calculate_product_health()
        print("✅ Product health calculated")
    else:
        print("ℹ️  Product health calculation script not found, skipping")

except Exception as e:
    print(f"⚠️  Error calculating product health: {e}")
    import traceback
    traceback.print_exc()
