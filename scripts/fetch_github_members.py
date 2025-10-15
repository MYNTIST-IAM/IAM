import os
import requests
import yaml
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Configuration
GITHUB_ORG_NAME = os.getenv('GITHUB_ORG_NAME')
GITHUB_PAT_TOKEN = os.getenv('GITHUB_PAT_TOKEN')
LEDGER_PATH = Path("security/token-ledger.yml")

# GitHub API headers
headers = {
    'Authorization': f'token {GITHUB_PAT_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}


def fetch_org_members():
    """Fetch all members of the GitHub organization"""
    url = f'https://api.github.com/orgs/{GITHUB_ORG_NAME}/members'
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching members: {e}")
        return []


def fetch_member_role(username):
    """Fetch the role of a specific member in the organization"""
    url = f'https://api.github.com/orgs/{GITHUB_ORG_NAME}/memberships/{username}'
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching role for {username}: {e}")
        return None


def update_token_ledger(members_data):
    """Update the token ledger with GitHub member information"""
    
    # Load existing ledger
    if LEDGER_PATH.exists():
        with open(LEDGER_PATH, 'r') as f:
            ledger = yaml.safe_load(f) or {'tokens': []}
    else:
        ledger = {'tokens': []}
    
    # Get existing token IDs
    existing_token_ids = {token['token_id'] for token in ledger['tokens']}
    
    # Process each member
    for member in members_data:
        username = member['login']
        member_id = str(member['id'])
        
        # Skip if token already exists
        if member_id in existing_token_ids:
            print(f"⏭️  Token for {username} (ID: {member_id}) already exists")
            continue
        
        # Fetch member role
        membership_info = fetch_member_role(username)
        
        if not membership_info:
            continue
        
        role = membership_info.get('role', 'member')
        state = membership_info.get('state', 'unknown')
        
        # Determine scope based on role
        if role == 'admin':
            scope = 'admin:org, repo, workflow, write:packages'
        else:
            scope = 'read:org, repo'
        
        # Create new token entry
        new_token = {
            'token_id': member_id,
            'owner': username,
            'scope': scope,
            'usage': 'GitHub Organization Access',
            'issued_on': datetime.now().strftime('%Y-%m-%d'),
            'expiry': 'N/A',  # GitHub user tokens don't expire
            'last_used': datetime.now().strftime('%Y-%m-%d'),
            'audit_trail': [f"org:{GITHUB_ORG_NAME}", f"role:{role}"],
            'survivability_score': 0.0,  # Will be calculated by scoring bot
            'entity_type': 'user',  # New field to identify this is a user token
            'role': role,  # Store the GitHub role
            'state': state  # Active/pending status
        }
        
        ledger['tokens'].append(new_token)
        print(f"✅ Added token for {username} (ID: {member_id}, Role: {role})")
    
    # Save updated ledger
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, 'w') as f:
        yaml.dump(ledger, f, default_flow_style=False, sort_keys=False)
    
    print(f"\n✅ Token ledger updated successfully at {LEDGER_PATH}")


def main():
    """Main function to orchestrate the member fetch and ledger update"""
    
    if not GITHUB_ORG_NAME or not GITHUB_PAT_TOKEN:
        print("❌ Error: GITHUB_ORG_NAME and GITHUB_PAT_TOKEN must be set in .env file")
        return
    
    print(f"🔍 Fetching members from organization: {GITHUB_ORG_NAME}")
    
    # Fetch all members
    members = fetch_org_members()
    
    if not members:
        print("⚠️  No members found or error occurred")
        return
    
    print(f"📋 Found {len(members)} member(s)")
    
    # Update token ledger with member information
    update_token_ledger(members)


if __name__ == '__main__':
    main()

