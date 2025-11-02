import os
import yaml
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
GITHUB_ORG_NAME = os.getenv('ORG_NAME')
GITHUB_PAT_TOKEN = os.getenv('PAT_TOKEN')
LEDGER_PATH = Path("security/token-ledger.yml")
AGENT_LEDGER_PATH = Path("agents/agent-ledger.yml")
WORKFLOWS_DIR = Path(".github/workflows")
API = "https://api.github.com"


def gh_headers():
    return {
        "Authorization": f"Bearer {GITHUB_PAT_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def load_yaml(path: Path):
    """Load YAML file, return empty dict if file doesn't exist"""
    if path.exists():
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_yaml(path: Path, data):
    """Save data to YAML file"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def get_workflow_permissions(workflow_content: str) -> str:
    """
    Extract permissions from workflow YAML content.
    Returns a comma-separated string of permissions (same format as token scope).
    """
    try:
        workflow_data = yaml.safe_load(workflow_content)
        if not workflow_data:
            return "read:repo"
        
        # Get permissions from workflow
        permissions = workflow_data.get("permissions", {})
        if not permissions:
            return "read:repo"  # Default permission
        
        # Convert to scope format
        perm_list = []
        for perm, value in permissions.items():
            if value in ["write", "read"]:
                perm_list.append(f"{perm}")
        
        # Common GitHub Actions permissions mapping
        if not perm_list:
            # If no explicit permissions, check jobs for hints
            if "contents: write" in workflow_content or "contents:write" in workflow_content:
                perm_list.append("repo")
            if "pull-requests: write" in workflow_content or "pull-requests:write" in workflow_content:
                perm_list.append("repo")
            if "issues: write" in workflow_content or "issues:write" in workflow_content:
                perm_list.append("repo")
            if "actions: write" in workflow_content or "actions:write" in workflow_content:
                perm_list.append("workflow")
            if "admin:org" in workflow_content or "admin:org" in str(permissions):
                perm_list.append("admin:org")
        
        if not perm_list:
            perm_list.append("read:repo")
        
        return ", ".join(perm_list) if perm_list else "read:repo"
    except Exception as e:
        print(f"⚠️  Error parsing workflow permissions: {e}")
        return "read:repo"


def find_associated_token(workflow_name: str, ledger: dict) -> str | None:
    """
    Try to find an associated token for this workflow.
    Logic: Match by workflow name patterns or use a default service account token.
    Returns token_id or None.
    """
    tokens = ledger.get("tokens", [])
    
    # Try to match workflow name with token owner or usage
    workflow_lower = workflow_name.lower()
    
    # Look for service account tokens that might match
    for token in tokens:
        owner = token.get("owner", "").lower()
        usage = token.get("usage", "").lower()
        entity_type = token.get("entity_type", "")
        
        # Match by usage pattern
        if entity_type == "service_account":
            if "ci" in workflow_lower and "ci" in usage:
                return str(token.get("token_id"))
            if "deploy" in workflow_lower and "deploy" in usage:
                return str(token.get("token_id"))
            if "auto" in workflow_lower and "auto" in usage:
                return str(token.get("token_id"))
    
    # If no match found, use the first service_account token as default
    for token in tokens:
        if token.get("entity_type") == "service_account":
            return str(token.get("token_id"))
    
    # Last resort: use first token
    if tokens:
        return str(tokens[0].get("token_id"))
    
    return None


def detect_agents_from_workflows():
    """
    Detect agents from GitHub Actions workflow files.
    Each workflow file represents a potential agent.
    """
    ledger = load_yaml(LEDGER_PATH)
    agent_ledger = load_yaml(AGENT_LEDGER_PATH)
    
    if "agents" not in agent_ledger:
        agent_ledger["agents"] = []
    
    existing_agents = {agent.get("agent_id") for agent in agent_ledger.get("agents", [])}
    detected_agents = []
    
    # Scan workflow files
    if not WORKFLOWS_DIR.exists():
        print("⚠️  No .github/workflows directory found")
        return
    
    workflow_files = list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))
    
    if not workflow_files:
        print("⚠️  No workflow files found")
        return
    
    print(f"🔍 Scanning {len(workflow_files)} workflow file(s)...")
    
    for workflow_path in workflow_files:
        try:
            with open(workflow_path, "r") as f:
                workflow_content = f.read()
            
            workflow_data = yaml.safe_load(workflow_content)
            if not workflow_data:
                continue
            
            workflow_name = workflow_data.get("name", workflow_path.stem)
            agent_id = f"agent-{workflow_path.stem}"
            
            # Skip if agent already exists
            if agent_id in existing_agents:
                print(f"⏭️  Agent {agent_id} ({workflow_name}) already exists")
                continue
            
            # Extract permissions/interaction scope
            interaction_scope = get_workflow_permissions(workflow_content)
            
            # Find associated token
            associated_token_id = find_associated_token(workflow_name, ledger)
            
            if not associated_token_id:
                print(f"⚠️  Warning: No associated token found for {workflow_name}, skipping")
                continue
            
            # Determine purpose from workflow content
            purpose = workflow_data.get("name", "GitHub Actions Workflow")
            jobs = workflow_data.get("jobs", {})
            if jobs:
                # Try to infer purpose from job names or steps
                job_names = list(jobs.keys())
                if len(job_names) > 0:
                    purpose = f"{purpose} ({', '.join(job_names[:2])})"
            
            # Create agent entry
            agent_entry = {
                "agent_id": agent_id,
                "agent_name": workflow_name,
                "associated_token_id": associated_token_id,
                "purpose": purpose,
                "interaction_scope": interaction_scope,
                "survivability_score": 0.0,  # Will be calculated by scoring bot
                "score_history": [],
                "last_scored": None,
                "audit_trail": [],
                "state": "active",
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "workflow_file": str(workflow_path.relative_to(Path(".")))
            }
            
            agent_ledger["agents"].append(agent_entry)
            detected_agents.append(agent_entry)
            print(f"✅ Detected agent: {agent_id} ({workflow_name}) → Token: {associated_token_id}")
            
        except Exception as e:
            print(f"❌ Error processing {workflow_path}: {e}")
            continue
    
    # Save updated agent ledger
    save_yaml(AGENT_LEDGER_PATH, agent_ledger)
    
    if detected_agents:
        print(f"\n✅ Detected {len(detected_agents)} new agent(s). Agent ledger updated.")
    else:
        print("\n✅ No new agents detected.")


def main():
    """Main function"""
    if not GITHUB_PAT_TOKEN:
        print("⚠️  Warning: PAT_TOKEN not set. Token association may be limited.")
    
    print("🤖 Detecting agents from GitHub Actions workflows...\n")
    detect_agents_from_workflows()


if __name__ == "__main__":
    main()

