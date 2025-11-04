import yaml
from pathlib import Path

PRODUCT_LEDGER_PATH = Path("products/product-ledger.yml")
TOKEN_LEDGER_PATH = Path("security/token-ledger.yml")
AGENT_LEDGER_PATH = Path("agents/agent-ledger.yml")


def load_yaml(path: Path):
    """Load YAML file, return empty dict if file doesn't exist"""
    if path.exists():
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def validate_products():
    """
    Validate that all products have valid linked_agents and linked_tokens.
    Returns True if all valid, False otherwise.
    """
    # Load ledgers
    product_ledger = load_yaml(PRODUCT_LEDGER_PATH)
    token_ledger = load_yaml(TOKEN_LEDGER_PATH)
    agent_ledger = load_yaml(AGENT_LEDGER_PATH)
    
    if not product_ledger or "products" not in product_ledger:
        print("ℹ️  No products found in product ledger")
        return True
    
    if not token_ledger or "tokens" not in token_ledger:
        print("⚠️  Warning: Token ledger not found or empty")
        token_ids = set()
    else:
        token_ids = {str(token.get("token_id")) for token in token_ledger.get("tokens", [])}
    
    if not agent_ledger or "agents" not in agent_ledger:
        print("⚠️  Warning: Agent ledger not found or empty")
        agent_ids = set()
    else:
        agent_ids = {agent.get("agent_id") for agent in agent_ledger.get("agents", [])}
    
    products = product_ledger.get("products", [])
    
    if not products:
        print("ℹ️  No products to validate")
        return True
    
    print(f"🔍 Validating {len(products)} product(s)...\n")
    
    errors = []
    warnings = []
    valid_count = 0
    
    for product in products:
        product_id = product.get("product_id", "unknown")
        product_name = product.get("product_name", "unknown")
        linked_agents = product.get("linked_agents", [])
        linked_tokens = product.get("linked_tokens", [])
        
        # Check if product has at least one dependency
        if not linked_agents and not linked_tokens:
            warnings.append({
                "product_id": product_id,
                "product_name": product_name,
                "message": "No linked agents or tokens",
                "severity": "warning"
            })
            continue
        
        # Validate linked tokens
        invalid_tokens = []
        for token_id in linked_tokens:
            token_id_str = str(token_id)
            if token_id_str not in token_ids:
                invalid_tokens.append(token_id_str)
        
        # Validate linked agents
        invalid_agents = []
        for agent_id in linked_agents:
            if agent_id not in agent_ids:
                invalid_agents.append(agent_id)
        
        if invalid_tokens or invalid_agents:
            errors.append({
                "product_id": product_id,
                "product_name": product_name,
                "invalid_tokens": invalid_tokens,
                "invalid_agents": invalid_agents,
                "severity": "error"
            })
        else:
            valid_count += 1
    
    # Print results
    if errors:
        print("❌ Validation Errors Found:\n")
        for error in errors:
            print(f"  Product: {error['product_id']} ({error['product_name']})")
            if error['invalid_tokens']:
                print(f"    Invalid tokens: {', '.join(error['invalid_tokens'])}")
            if error['invalid_agents']:
                print(f"    Invalid agents: {', '.join(error['invalid_agents'])}")
            print()
    
    if warnings:
        print("⚠️  Warnings:\n")
        for warning in warnings:
            print(f"  Product: {warning['product_id']} ({warning['product_name']})")
            print(f"    Warning: {warning['message']}")
            print()
    
    if valid_count > 0:
        print(f"✅ {valid_count} product(s) validated successfully")
    
    if errors:
        print(f"\n❌ Validation failed: {len(errors)} error(s) found")
        return False
    else:
        print("\n✅ All products validated successfully")
        return True


def check_orphaned_products():
    """
    Check for products whose dependencies have all been removed.
    """
    product_ledger = load_yaml(PRODUCT_LEDGER_PATH)
    token_ledger = load_yaml(TOKEN_LEDGER_PATH)
    agent_ledger = load_yaml(AGENT_LEDGER_PATH)
    
    if not product_ledger or "products" not in product_ledger:
        return []
    
    token_ids = {str(token.get("token_id")) for token in token_ledger.get("tokens", [])} if token_ledger else set()
    agent_ids = {agent.get("agent_id") for agent in agent_ledger.get("agents", [])} if agent_ledger else set()
    
    orphaned = []
    
    for product in product_ledger.get("products", []):
        linked_agents = product.get("linked_agents", [])
        linked_tokens = product.get("linked_tokens", [])
        
        # Check if all dependencies are missing
        valid_agents = [a for a in linked_agents if a in agent_ids]
        valid_tokens = [str(t) for t in linked_tokens if str(t) in token_ids]
        
        if not valid_agents and not valid_tokens and (linked_agents or linked_tokens):
            orphaned.append(product)
    
    return orphaned


def main():
    """Main validation function"""
    print("🔍 Product Ledger Validation\n")
    print("=" * 50)
    
    if not PRODUCT_LEDGER_PATH.exists():
        print(f"⚠️  Product ledger not found at {PRODUCT_LEDGER_PATH}")
        print("   Run 'python scripts/detect_products.py' to create products from repositories")
        return
    
    is_valid = validate_products()
    
    # Check for orphaned products
    orphaned = check_orphaned_products()
    if orphaned:
        print(f"\n⚠️  Found {len(orphaned)} orphaned product(s) (all dependencies removed)")
        for product in orphaned:
            print(f"  - {product.get('product_id')} ({product.get('product_name')})")
    
    # Exit with appropriate code
    if not is_valid:
        exit(1)


if __name__ == "__main__":
    main()

