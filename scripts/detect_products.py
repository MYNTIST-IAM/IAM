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
PRODUCT_LEDGER_PATH = Path("products/product-ledger.yml")
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


def fetch_org_repos():
    """Fetch all repositories in the organization"""
    if not GITHUB_PAT_TOKEN or not GITHUB_ORG_NAME:
        return []
    
    url = f"{API}/orgs/{GITHUB_ORG_NAME}/repos"
    
    try:
        response = requests.get(url, headers=gh_headers(), params={"per_page": 100})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error fetching repositories: {e}")
        return []


def detect_products_from_repos():
    """
    Detect products from GitHub organization repositories.
    Each repository can be considered a product.
    """
    token_ledger = load_yaml(LEDGER_PATH)
    agent_ledger = load_yaml(AGENT_LEDGER_PATH)
    product_ledger = load_yaml(PRODUCT_LEDGER_PATH)
    
    if "products" not in product_ledger:
        product_ledger["products"] = []
    
    existing_products = {product.get("product_id") for product in product_ledger.get("products", [])}
    detected_products = []
    
    # Fetch repositories from GitHub
    if not GITHUB_PAT_TOKEN or not GITHUB_ORG_NAME:
        print("⚠️  Warning: PAT_TOKEN or ORG_NAME not set. Cannot auto-detect products from GitHub.")
        print("   Products can be manually added to products/product-ledger.yml")
        return
    
    print(f"🔍 Fetching repositories from organization: {GITHUB_ORG_NAME}...")
    repos = fetch_org_repos()
    
    if not repos:
        print("⚠️  No repositories found or error occurred")
        return
    
    print(f"📋 Found {len(repos)} repository/repositories")
    
    # Get all agent IDs and token IDs for linking
    all_agent_ids = {agent.get("agent_id") for agent in agent_ledger.get("agents", [])}
    all_token_ids = {str(token.get("token_id")) for token in token_ledger.get("tokens", [])}
    
    for repo in repos:
        try:
            repo_name = repo.get("name", "")
            repo_id = str(repo.get("id", ""))
            product_id = f"product-{repo_name.lower().replace(' ', '-')}"
            
            # Skip if product already exists
            if product_id in existing_products:
                print(f"⏭️  Product {product_id} ({repo_name}) already exists")
                continue
            
            # Determine responsible team (default to org name or repo owner)
            responsible_team = repo.get("owner", {}).get("login", GITHUB_ORG_NAME) or "Unknown"
            
            # Try to link agents that might be related to this repo
            # This is a simple heuristic - in practice, you might want more sophisticated matching
            linked_agents = []
            linked_tokens = []
            
            # For now, we'll link all agents and tokens (can be refined later)
            # Or you can leave empty for manual linking
            # linked_agents = list(all_agent_ids)  # Uncomment to auto-link all agents
            # linked_tokens = list(all_token_ids)  # Uncomment to auto-link all tokens
            
            # Create product entry
            product_entry = {
                "product_id": product_id,
                "product_name": repo_name,
                "responsible_team": responsible_team,
                "linked_agents": linked_agents,  # Empty by default - requires manual linking
                "linked_tokens": linked_tokens,  # Empty by default - requires manual linking
                "survivability_health": 0.0,  # Will be calculated by health calculation script
                "health_status": "Unknown",  # Will be calculated
                "last_calculated": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "repo_url": repo.get("html_url", ""),
                "repo_id": repo_id,
                "auto_detected": True  # Mark as auto-detected
            }
            
            product_ledger["products"].append(product_entry)
            detected_products.append(product_entry)
            print(f"✅ Detected product: {product_id} ({repo_name}) → Team: {responsible_team}")
            
        except Exception as e:
            print(f"❌ Error processing repository {repo.get('name', 'unknown')}: {e}")
            continue
    
    # Save updated product ledger
    save_yaml(PRODUCT_LEDGER_PATH, product_ledger)
    
    if detected_products:
        print(f"\n✅ Detected {len(detected_products)} new product(s). Product ledger updated.")
        print("   Note: Products are auto-detected but require manual linking to agents/tokens.")
        print("   Edit products/product-ledger.yml to add linked_agents and linked_tokens.")
    else:
        print("\n✅ No new products detected.")


def main():
    """Main function"""
    if not GITHUB_PAT_TOKEN:
        print("⚠️  Warning: PAT_TOKEN not set. Auto-detection will be limited.")
        print("   Products can be manually added to products/product-ledger.yml")
    
    print("📦 Detecting products from GitHub repositories...\n")
    detect_products_from_repos()


if __name__ == "__main__":
    main()

