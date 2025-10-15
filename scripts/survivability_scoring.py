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
def calculate_score(scope, used, drift, audit):
    """Implements: S = (1 / Q_perms) * cos(scope_drift) * audit_memory"""
    granted = len(scope.split(','))  # Calculate granted permissions based on scope
    if used == 0:
        used = 1  # avoid divide-by-zero
    Q_perms = granted / used
    audit_memory = 1.0 if audit else 0.5
    S = (1 / Q_perms) * math.cos(drift) * audit_memory
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
        token.get("audit_trail", [])  # Audit trail is used as a boolean indicator
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

    results.append({
        "token_id": token["token_id"],
        "owner": token["owner"],
        "survivability_score": S,
        "status": status,
        "score_history": score_history
    })


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
    f.write("| Token ID | Owner | Current Score | Status | Trend (Last 7) |\n")
    f.write("|----------|-------|---------------|--------|----------------|\n")
    for r in results:
        history_scores = [h["score"] for h in r["score_history"]]
        trend = " → ".join([str(s) for s in history_scores])
        f.write(f"| {r['token_id']} | {r['owner']} | {r['survivability_score']} | {r['status']} | {trend} |\n")

print("✅ Survivability scoring complete. Reports generated in /reports/")
print(f"📊 Score history maintained (max {MAX_HISTORY_ENTRIES} entries per token)")
