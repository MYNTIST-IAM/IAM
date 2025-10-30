import yaml
import math
import json
from pathlib import Path
from datetime import datetime

# --- Config paths ---
LEDGER_PATH = Path("security/token-ledger.yml")
REPORT_JSON = Path("reports/token_health.json")
REPORT_MD = Path("reports/token_health_report.md")
HISTORY_JSON = Path("reports/score_history.json")
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
    
    # Cap the score at 2.0 to prevent unrealistic scores
    S = min(2.0, S)
    
    return round(S, 3)


def get_status(score):
    if score >= 0.8:
        return "Healthy"
    elif score >= 0.5:
        return "Degrading"
    else:
        return "Critical"


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
