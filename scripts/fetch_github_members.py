import os
import requests
import yaml
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Configuration
GITHUB_ORG_NAME = os.getenv('ORG_NAME')
GITHUB_PAT_TOKEN = os.getenv('PAT_TOKEN')
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


def fetch_org_repos():
    """Fetch all repositories in the organization"""
    url = f'https://api.github.com/orgs/{GITHUB_ORG_NAME}/repos'
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching repositories: {e}")
        return []


def fetch_member_repo_access(username):
    """Fetch repository access for a specific member"""
    # Get all org repos first
    repos = fetch_org_repos()
    if not repos:
        return []
    
    repo_access = []
    
    for repo in repos:
        repo_name = repo['name']
        repo_id = repo['id']
        
        # Check if user has access to this repo
        url = f'https://api.github.com/repos/{GITHUB_ORG_NAME}/{repo_name}/collaborators/{username}'
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 204:  # User has access
                # Get permission level
                perm_url = f'https://api.github.com/repos/{GITHUB_ORG_NAME}/{repo_name}/collaborators/{username}/permission'
                perm_response = requests.get(perm_url, headers=headers)
                
                if perm_response.status_code == 200:
                    perm_data = perm_response.json()
                    permission = perm_data.get('permission', 'read')
                else:
                    permission = 'read'  # Default to read if we can't get permission level
                
                repo_access.append({
                    'repo_id': repo_id,
                    'repo_name': repo_name,
                    'permission': permission,
                    'private': repo['private']
                })
                
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Error checking access to {repo_name} for {username}: {e}")
            continue
    
    return repo_access


def update_token_ledger(members_data):
    """Update the token ledger with GitHub member information"""
    
    # Load existing ledger
    if LEDGER_PATH.exists():
        with open(LEDGER_PATH, 'r') as f:
            ledger = yaml.safe_load(f) or {'tokens': []}
    else:
        ledger = {'tokens': []}
    
    # Process each member
    for member in members_data:
        username = member['login']
        member_id = str(member['id'])
        
        # Fetch member role (always fetch latest from GitHub)
        membership_info = fetch_member_role(username)
        
        if not membership_info:
            continue
        
        role = membership_info.get('role', 'member')
        state = membership_info.get('state', 'unknown')
        
        # Fetch repository access for this member
        print(f"🔍 Checking repository access for {username}...")
        repo_access = fetch_member_repo_access(username)
        
        # Determine scope based on role and repo access
        # Note: GitHub API returns 'admin' for organization admins and 'direct_member' for regular members
        # Owner role is typically the organization owner (only one owner per org)
        if role in ['admin', 'owner']:
            scope = 'admin:org, repo, workflow, write:packages'
        else:
            scope = 'read:org, repo'
        
        # Calculate repository access summary
        repo_count = len(repo_access)
        private_repo_count = sum(1 for repo in repo_access if repo['private'])
        admin_repo_count = sum(1 for repo in repo_access if repo['permission'] in ['admin', 'maintain'])
        write_repo_count = sum(1 for repo in repo_access if repo['permission'] in ['write', 'admin', 'maintain'])
        
        # Check if token already exists
        existing_token = None
        for token in ledger['tokens']:
            if str(token.get('token_id')) == member_id:
                existing_token = token
                break
        
        if existing_token:
            # Update existing token with latest role and repo access
            old_role = existing_token.get('role', 'unknown')
            existing_token['role'] = role
            existing_token['state'] = state
            existing_token['scope'] = scope
            existing_token['repository_access'] = repo_access
            existing_token['repo_access_summary'] = {
                'total_repos': repo_count,
                'private_repos': private_repo_count,
                'admin_repos': admin_repo_count,
                'write_repos': write_repo_count
            }
            
            # Update role in audit_trail if it changed
            audit_trail = existing_token.get('audit_trail', [])
            if isinstance(audit_trail, list):
                # Update or add role entry
                role_entry = f"role:{role}"
                # Remove old role entry if exists
                audit_trail = [e for e in audit_trail if not (isinstance(e, str) and e.startswith('role:'))]
                # Add new role entry
                audit_trail.append(role_entry)
                existing_token['audit_trail'] = audit_trail
            
            if old_role != role:
                print(f"🔄 Updated token for {username} (ID: {member_id}): Role changed from {old_role} → {role}, Repos: {repo_count}")
            else:
                print(f"🔄 Updated token for {username} (ID: {member_id}): Role: {role}, Repos: {repo_count}")
        else:
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
                'state': state,  # Active/pending status
                'repository_access': repo_access,  # Detailed repo access
                'repo_access_summary': {
                    'total_repos': repo_count,
                    'private_repos': private_repo_count,
                    'admin_repos': admin_repo_count,
                    'write_repos': write_repo_count
                }
            }
            
            ledger['tokens'].append(new_token)
            print(f"✅ Added token for {username} (ID: {member_id}, Role: {role}, Repos: {repo_count}, Private: {private_repo_count}, Admin: {admin_repo_count})")
    
    # Save updated ledger
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, 'w') as f:
        yaml.dump(ledger, f, default_flow_style=False, sort_keys=False)
    
    print(f"\n✅ Token ledger updated successfully at {LEDGER_PATH}")


def main():
    """Main function to orchestrate the member fetch and ledger update"""
    
    if not GITHUB_ORG_NAME or not GITHUB_PAT_TOKEN:
        print("❌ Error: ORG_NAME and PAT_TOKEN must be set in .env file")
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

