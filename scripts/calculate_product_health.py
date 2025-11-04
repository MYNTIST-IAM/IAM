import yaml
import json
from pathlib import Path
from datetime import datetime

# --- Config paths ---
PRODUCT_LEDGER_PATH = Path("products/product-ledger.yml")
TOKEN_LEDGER_PATH = Path("security/token-ledger.yml")
AGENT_LEDGER_PATH = Path("agents/agent-ledger.yml")
TOKEN_REPORT_JSON = Path("reports/token_health.json")
AGENT_REPORT_JSON = Path("reports/agent_health.json")
PRODUCT_REPORT_JSON = Path("reports/product_health.json")
PRODUCT_REPORT_MD = Path("reports/product_health_report.md")


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


def get_status_from_score(score: float) -> str:
    """Get health status from score"""
    if score >= 0.8:
        return "Green"
    elif score >= 0.2:
        return "Yellow"
    else:
        return "Red"


def calculate_product_health():
    """
    Calculate aggregate survivability health for all products.
    Uses average of all linked token and agent scores.
    This function can be called independently or from survivability_scoring.py
    """
    # Load ledgers
    product_ledger = load_yaml(PRODUCT_LEDGER_PATH)
    token_ledger = load_yaml(TOKEN_LEDGER_PATH)
    agent_ledger = load_yaml(AGENT_LEDGER_PATH)
    
    # Load health reports
    token_scores = {}
    agent_scores = {}
    
    if TOKEN_REPORT_JSON.exists():
        with open(TOKEN_REPORT_JSON, "r") as f:
            token_report = json.load(f)
            token_scores = {
                str(r["token_id"]): r.get("survivability_score", 0.0)
                for r in token_report
            }
    
    if AGENT_REPORT_JSON.exists():
        with open(AGENT_REPORT_JSON, "r") as f:
            agent_report = json.load(f)
            agent_scores = {
                r["agent_id"]: r.get("survivability_score", 0.0)
                for r in agent_report
            }
    
    if "products" not in product_ledger:
        print("ℹ️  No products found in product ledger")
        return
    
    products = product_ledger.get("products", [])
    
    if not products:
        print("ℹ️  No products to calculate health for")
        return
    
    print(f"📊 Calculating health for {len(products)} product(s)...")
    
    product_results = []
    updated_products = []
    
    for product in products:
        product_id = product.get("product_id")
        product_name = product.get("product_name", "Unknown")
        linked_agents = product.get("linked_agents", [])
        linked_tokens = product.get("linked_tokens", [])
        
        # Collect scores from linked dependencies
        dependency_scores = []
        missing_dependencies = []
        
        # Collect token scores
        for token_id in linked_tokens:
            token_id_str = str(token_id)
            if token_id_str in token_scores:
                dependency_scores.append(token_scores[token_id_str])
            else:
                missing_dependencies.append(f"token:{token_id_str}")
        
        # Collect agent scores
        for agent_id in linked_agents:
            if agent_id in agent_scores:
                dependency_scores.append(agent_scores[agent_id])
            else:
                missing_dependencies.append(f"agent:{agent_id}")
        
        # Calculate aggregate health
        if not dependency_scores:
            # No dependencies or all missing
            if not linked_agents and not linked_tokens:
                survivability_health = 0.0
                health_status = "Unknown"
                print(f"⚠️  Product {product_id} has no linked dependencies")
            else:
                survivability_health = 0.0
                health_status = "Red"
                print(f"⚠️  Product {product_id} has missing dependencies: {', '.join(missing_dependencies)}")
        else:
            # Calculate average of all dependency scores
            survivability_health = sum(dependency_scores) / len(dependency_scores)
            health_status = get_status_from_score(survivability_health)
        
        # Update product with calculated health
        product["survivability_health"] = round(survivability_health, 3)
        product["health_status"] = health_status
        product["last_calculated"] = datetime.now().isoformat()
        product["updated_at"] = datetime.now().isoformat()
        
        updated_products.append(product)
        
        # Prepare result data
        result_data = {
            "product_id": product_id,
            "product_name": product_name,
            "responsible_team": product.get("responsible_team", "Unknown"),
            "survivability_health": round(survivability_health, 3),
            "health_status": health_status,
            "linked_agents_count": len(linked_agents),
            "linked_tokens_count": len(linked_tokens),
            "dependency_scores": dependency_scores,
            "missing_dependencies": missing_dependencies
        }
        
        product_results.append(result_data)
    
    # Save updated product ledger
    product_ledger["products"] = updated_products
    save_yaml(PRODUCT_LEDGER_PATH, product_ledger)
    print(f"✅ Updated product ledger with calculated health scores")
    
    # Write product health JSON report
    if product_results:
        PRODUCT_REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
        with open(PRODUCT_REPORT_JSON, "w") as f:
            json.dump(product_results, f, indent=2)
        
        # Write product health Markdown report
        with open(PRODUCT_REPORT_MD, "w") as f:
            f.write("# Product Health Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
            f.write("| Product ID | Product Name | Team | Health | Status | Dependencies |\n")
            f.write("|------------|--------------|------|--------|--------|---------------|\n")
            for r in product_results:
                deps_count = r["linked_agents_count"] + r["linked_tokens_count"]
                status_emoji = {
                    "Green": "🟢",
                    "Yellow": "🟡",
                    "Red": "🔴",
                    "Unknown": "⚪"
                }.get(r["health_status"], "⚪")
                f.write(f"| {r['product_id']} | {r['product_name']} | {r['responsible_team']} | {r['survivability_health']} | {status_emoji} {r['health_status']} | {deps_count} ({r['linked_agents_count']} agents, {r['linked_tokens_count']} tokens) |\n")
        
        print(f"✅ Product health reports generated ({len(product_results)} products)")
    else:
        print("ℹ️  No products to report")


def main():
    """Main function"""
    print("📊 Calculating Product Health\n")
    print("=" * 50)
    calculate_product_health()


if __name__ == "__main__":
    main()

