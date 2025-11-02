import yaml
from pathlib import Path

LEDGER_PATH = Path("security/token-ledger.yml")
AGENT_LEDGER_PATH = Path("agents/agent-ledger.yml")


def load_yaml(path: Path):
    """Load YAML file, return empty dict if file doesn't exist"""
    if path.exists():
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def validate_agents():
    """
    Validate that all agents have valid associated_token_id references.
    Returns list of validation errors.
    """
    # Load ledgers
    token_ledger = load_yaml(LEDGER_PATH)
    agent_ledger = load_yaml(AGENT_LEDGER_PATH)
    
    if not token_ledger or "tokens" not in token_ledger:
        print("⚠️  Warning: Token ledger not found or empty")
        return
    
    if not agent_ledger or "agents" not in agent_ledger:
        print("ℹ️  No agents found in agent ledger")
        return
    
    # Create token ID lookup
    token_ids = {str(token.get("token_id")) for token in token_ledger.get("tokens", [])}
    
    agents = agent_ledger.get("agents", [])
    
    if not agents:
        print("ℹ️  No agents to validate")
        return
    
    print(f"🔍 Validating {len(agents)} agent(s)...\n")
    
    errors = []
    warnings = []
    valid_count = 0
    
    for agent in agents:
        agent_id = agent.get("agent_id", "unknown")
        agent_name = agent.get("agent_name", "unknown")
        associated_token_id = agent.get("associated_token_id")
        
        # Check if associated_token_id exists
        if not associated_token_id:
            errors.append({
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": "Missing associated_token_id",
                "severity": "error"
            })
            continue
        
        # Check if token exists in ledger
        token_id_str = str(associated_token_id)
        if token_id_str not in token_ids:
            errors.append({
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"Associated token {token_id_str} not found in token ledger",
                "severity": "error",
                "associated_token_id": token_id_str
            })
            continue
        
        # Check for orphaned tokens (token exists but agent references it)
        # This is just informational
        valid_count += 1
    
    # Print results
    if errors:
        print("❌ Validation Errors Found:\n")
        for error in errors:
            print(f"  Agent: {error['agent_id']} ({error['agent_name']})")
            print(f"  Error: {error['error']}")
            if 'associated_token_id' in error:
                print(f"  Token ID: {error['associated_token_id']}")
            print()
    
    if warnings:
        print("⚠️  Warnings:\n")
        for warning in warnings:
            print(f"  Agent: {warning['agent_id']} ({warning['agent_name']})")
            print(f"  Warning: {warning['message']}")
            print()
    
    if valid_count > 0:
        print(f"✅ {valid_count} agent(s) validated successfully")
    
    if errors:
        print(f"\n❌ Validation failed: {len(errors)} error(s) found")
        return False
    else:
        print("\n✅ All agents validated successfully")
        return True


def check_orphaned_agents():
    """
    Check for agents whose associated tokens have been removed.
    """
    token_ledger = load_yaml(LEDGER_PATH)
    agent_ledger = load_yaml(AGENT_LEDGER_PATH)
    
    if not agent_ledger or "agents" not in agent_ledger:
        return []
    
    token_ids = {str(token.get("token_id")) for token in token_ledger.get("tokens", [])}
    orphaned = []
    
    for agent in agent_ledger.get("agents", []):
        associated_token_id = agent.get("associated_token_id")
        if associated_token_id and str(associated_token_id) not in token_ids:
            orphaned.append(agent)
    
    return orphaned


def main():
    """Main validation function"""
    print("🔍 Agent Ledger Validation\n")
    print("=" * 50)
    
    if not AGENT_LEDGER_PATH.exists():
        print(f"⚠️  Agent ledger not found at {AGENT_LEDGER_PATH}")
        print("   Run 'python scripts/detect_agents.py' to create agents from workflows")
        return
    
    if not LEDGER_PATH.exists():
        print(f"❌ Token ledger not found at {LEDGER_PATH}")
        print("   Agent validation requires token ledger to exist")
        return
    
    is_valid = validate_agents()
    
    # Check for orphaned agents
    orphaned = check_orphaned_agents()
    if orphaned:
        print(f"\n⚠️  Found {len(orphaned)} orphaned agent(s) (token removed)")
        for agent in orphaned:
            print(f"  - {agent.get('agent_id')} ({agent.get('agent_name')}) → Token {agent.get('associated_token_id')} not found")
    
    # Exit with appropriate code
    if not is_valid:
        exit(1)


if __name__ == "__main__":
    main()

