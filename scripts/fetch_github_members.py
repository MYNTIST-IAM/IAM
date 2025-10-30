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
    """Fetch all repositories in the organization with full details"""
    url = f'https://api.github.com/orgs/{GITHUB_ORG_NAME}/repos'
    all_repos = []
    page = 1
    per_page = 100
    
    try:
        while True:
            params = {'page': page, 'per_page': per_page, 'type': 'all'}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            repos = response.json()
            
            if not repos:
                break
            
            all_repos.extend(repos)
            
            # If we got less than per_page, we're done
            if len(repos) < per_page:
                break
            
            page += 1
        
        print(f"📦 Found {len(all_repos)} repository(s) in organization")
        return all_repos
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching repositories: {e}")
        return []


def fetch_org_teams():
    """Fetch all teams in the organization"""
    url = f'https://api.github.com/orgs/{GITHUB_ORG_NAME}/teams'
    all_teams = []
    page = 1
    per_page = 100
    
    try:
        while True:
            params = {'page': page, 'per_page': per_page}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            teams = response.json()
            
            if not teams:
                break
            
            all_teams.extend(teams)
            
            if len(teams) < per_page:
                break
            
            page += 1
        
        print(f"👥 Found {len(all_teams)} team(s) in organization")
        return all_teams
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching teams: {e}")
        return []


def fetch_team_members(team_slug):
    """Fetch all members of a specific team"""
    url = f'https://api.github.com/orgs/{GITHUB_ORG_NAME}/teams/{team_slug}/members'
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error fetching team members for {team_slug}: {e}")
        return []


def fetch_team_repo_permissions(team_slug, repo_name):
    """Fetch a team's permission level for a specific repository"""
    url = f'https://api.github.com/orgs/{GITHUB_ORG_NAME}/teams/{team_slug}/repos/{GITHUB_ORG_NAME}/{repo_name}'
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get('permission', 'none')
        return 'none'
    except requests.exceptions.RequestException as e:
        return 'none'


def fetch_user_last_activity(username, repos_list):
    """Fetch the most recent activity date for a GitHub user across organization repos"""
    if not repos_list:
        return None
    
    latest_date = None
    
    for repo in repos_list:
        repo_name = repo['name']
        
        # Check recent commits by this user
        # IMPORTANT: Verify the commit author actually matches this username
        commits_url = f'https://api.github.com/repos/{GITHUB_ORG_NAME}/{repo_name}/commits'
        try:
            params = {'author': username, 'per_page': 10}  # Get more to verify author
            response = requests.get(commits_url, headers=headers, params=params)
            if response.status_code == 200:
                commits = response.json()
                for commit in commits:
                    # Verify the commit author/login actually matches the username
                    author_info = commit.get('author')
                    if author_info and author_info.get('login') == username:
                        commit_date_str = commit['commit']['author']['date']
                        # Parse ISO 8601 date - handle timezone
                        try:
                            # GitHub returns dates like "2025-10-31T12:00:00Z"
                            if commit_date_str.endswith('Z'):
                                commit_date_str = commit_date_str.replace('Z', '+00:00')
                            commit_date = datetime.fromisoformat(commit_date_str)
                            # Convert to naive datetime for comparison
                            if commit_date.tzinfo:
                                commit_date = commit_date.replace(tzinfo=None)
                            if latest_date is None or commit_date > latest_date:
                                latest_date = commit_date
                                break  # Found valid commit, no need to check more
                        except (ValueError, AttributeError):
                            continue
        except (requests.exceptions.RequestException, ValueError) as e:
            continue
        
        # Check recent PRs created by this user
        # IMPORTANT: Verify the PR creator actually matches this username
        prs_url = f'https://api.github.com/repos/{GITHUB_ORG_NAME}/{repo_name}/pulls'
        try:
            params = {'state': 'all', 'per_page': 10}  # Get more to verify creator
            response = requests.get(prs_url, headers=headers, params=params)
            if response.status_code == 200:
                prs = response.json()
                for pr in prs:
                    # Verify the PR creator/user actually matches the username
                    pr_user = pr.get('user', {})
                    pr_creator_login = pr_user.get('login') if pr_user else None
                    if pr_creator_login == username:
                        pr_date_str = pr.get('updated_at') or pr.get('created_at')
                        if pr_date_str:
                            try:
                                # GitHub returns dates like "2025-10-31T12:00:00Z"
                                if pr_date_str.endswith('Z'):
                                    pr_date_str = pr_date_str.replace('Z', '+00:00')
                                pr_date = datetime.fromisoformat(pr_date_str)
                                # Convert to naive datetime for comparison
                                if pr_date.tzinfo:
                                    pr_date = pr_date.replace(tzinfo=None)
                                if latest_date is None or pr_date > latest_date:
                                    latest_date = pr_date
                                    break  # Found valid PR, no need to check more
                            except (ValueError, AttributeError):
                                continue
        except (requests.exceptions.RequestException, ValueError) as e:
            continue
    
    return latest_date


def build_repo_access_map():
    """Build a cached map of all repos and team memberships for efficient access lookup"""
    print("📦 Building repository and team access map...")
    
    # Fetch all repos and teams once
    repos = fetch_org_repos()
    teams = fetch_org_teams()
    
    # Build team -> members map
    team_members_map = {}
    for team in teams:
        team_slug = team['slug']
        team_members = fetch_team_members(team_slug)
        team_members_map[team_slug] = [member['login'] for member in team_members]
    
    # Build team -> repo permissions map
    team_repo_perms = {}
    for team in teams:
        team_slug = team['slug']
        team_repo_perms[team_slug] = {}
        for repo in repos:
            repo_name = repo['name']
            perm = fetch_team_repo_permissions(team_slug, repo_name)
            if perm and perm != 'none':
                team_repo_perms[team_slug][repo_name] = perm
    
    return repos, team_members_map, team_repo_perms


def get_member_repo_access_from_cache(username, repos, team_members_map, team_repo_perms):
    """Get repository access for a member using cached data"""
    repo_access = []
    
    # Find teams this user belongs to
    user_teams = [team_slug for team_slug, members in team_members_map.items() if username in members]
    
    for repo in repos:
        repo_name = repo['name']
        repo_id = repo['id']
        repo_private = repo.get('private', False)
        repo_default_branch = repo.get('default_branch', 'main')
        
        permission = None
        access_source = None
        
        # Check team-based access
        for team_slug in user_teams:
            if repo_name in team_repo_perms.get(team_slug, {}):
                team_perm = team_repo_perms[team_slug][repo_name]
                permission_levels = {'none': 0, 'pull': 1, 'triage': 2, 'push': 3, 'maintain': 4, 'admin': 5}
                if permission is None or permission_levels.get(team_perm, 0) > permission_levels.get(permission, 0):
                    permission = team_perm
                    access_source = f"team:{team_slug}"
        
        # Check direct collaborator access (overrides team access)
        direct_perm_url = f'https://api.github.com/repos/{GITHUB_ORG_NAME}/{repo_name}/collaborators/{username}/permission'
        try:
            direct_response = requests.get(direct_perm_url, headers=headers)
            if direct_response.status_code == 200:
                direct_data = direct_response.json()
                direct_perm = direct_data.get('permission', 'none')
                if direct_perm and direct_perm != 'none':
                    # Map GitHub API permission names to standard format
                    # API returns: read, write, admin -> convert to: pull, push, admin
                    perm_mapping = {
                        'read': 'pull',
                        'write': 'push',
                        'admin': 'admin'
                    }
                    permission = perm_mapping.get(direct_perm, direct_perm)
                    access_source = "direct"
        except requests.exceptions.RequestException:
            pass
        
        # If user has access, add it to the list
        if permission and permission != 'none':
            repo_access.append({
                'repo_id': repo_id,
                'repo_name': repo_name,
                'permission': permission,
                'private': repo_private,
                'default_branch': repo_default_branch,
                'access_source': access_source
            })
    
    return repo_access


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
    
    # Build cached access map (do this once for all members)
    repos, team_members_map, team_repo_perms = build_repo_access_map()
    
    # Process each member
    for member in members_data:
        username = member['login']
        member_id = str(member['id'])
        
        # Check if token already exists
        existing_token = None
        if member_id in existing_token_ids:
            # Find existing token
            for token in ledger['tokens']:
                if token['token_id'] == member_id:
                    existing_token = token
                    break
        
        # Fetch member role
        membership_info = fetch_member_role(username)
        
        if not membership_info:
            continue
        
        role = membership_info.get('role', 'member')
        state = membership_info.get('state', 'unknown')
        
        # Fetch repository access for this member using cached data
        print(f"🔍 Checking repository access for {username}...")
        repo_access = get_member_repo_access_from_cache(username, repos, team_members_map, team_repo_perms)
        
        # Fetch actual last activity date from GitHub (commits, PRs, etc.)
        print(f"   📅 Checking recent activity for {username}...")
        last_activity_date = fetch_user_last_activity(username, repos)
        
        # Determine last_used date - use actual activity if available, otherwise use today
        if last_activity_date:
            # Ensure it's a naive datetime
            if last_activity_date.tzinfo:
                last_activity_date = last_activity_date.replace(tzinfo=None)
            last_used_str = last_activity_date.strftime('%Y-%m-%d')
            days_since_activity = (datetime.now() - last_activity_date).days
            print(f"   ✅ Last activity: {last_used_str} ({days_since_activity} days ago)")
        else:
            # No recent activity found, use today as fallback (they're active member)
            last_used_str = datetime.now().strftime('%Y-%m-%d')
            print(f"   ⚠️  No recent activity found, using current date")
        
        # Determine scope based on role and repo access
        if role == 'admin':
            scope = 'admin:org, repo, workflow, write:packages'
        else:
            scope = 'read:org, repo'
        
        # Calculate detailed repository access summary
        repo_count = len(repo_access)
        private_repo_count = sum(1 for repo in repo_access if repo['private'])
        public_repo_count = repo_count - private_repo_count
        
        # Count by permission level (GitHub uses: pull, triage, push, maintain, admin)
        # Also handle legacy "read" permission (map to pull)
        pull_repo_count = sum(1 for repo in repo_access if repo['permission'] in ['pull', 'read'])
        triage_repo_count = sum(1 for repo in repo_access if repo['permission'] == 'triage')
        push_repo_count = sum(1 for repo in repo_access if repo['permission'] in ['push', 'write'])
        maintain_repo_count = sum(1 for repo in repo_access if repo['permission'] == 'maintain')
        admin_repo_count = sum(1 for repo in repo_access if repo['permission'] == 'admin')
        
        # Normalize permission values in repo_access (read -> pull, write -> push)
        for repo in repo_access:
            if repo['permission'] == 'read':
                repo['permission'] = 'pull'
            elif repo['permission'] == 'write':
                repo['permission'] = 'push'
        
        # Write access includes push, maintain, and admin
        write_repo_count = push_repo_count + maintain_repo_count + admin_repo_count
        
        # Update existing token or create new one
        if existing_token:
            # Update existing token with new repository access info
            existing_token['repository_access'] = repo_access
            existing_token['repo_access_summary'] = {
                'total_repos': repo_count,
                'private_repos': private_repo_count,
                'public_repos': public_repo_count,
                'pull_repos': pull_repo_count,
                'triage_repos': triage_repo_count,
                'push_repos': push_repo_count,
                'maintain_repos': maintain_repo_count,
                'admin_repos': admin_repo_count,
                'write_repos': write_repo_count
            }
            existing_token['role'] = role
            existing_token['state'] = state
            # Update last_used with actual activity date
            existing_token['last_used'] = last_used_str
            action = "Updated"
        else:
            # Create new token entry
            new_token = {
                'token_id': member_id,
                'owner': username,
                'scope': scope,
                'usage': 'GitHub Organization Access',
                'issued_on': datetime.now().strftime('%Y-%m-%d'),
                'expiry': 'N/A',  # GitHub user tokens don't expire
                'last_used': last_used_str,  # Use actual activity date
                'audit_trail': [f"org:{GITHUB_ORG_NAME}", f"role:{role}"],
                'survivability_score': 0.0,  # Will be calculated by scoring bot
                'entity_type': 'user',  # New field to identify this is a user token
                'role': role,  # Store the GitHub role
                'state': state,  # Active/pending status
                'repository_access': repo_access,  # Detailed repo access with permissions
                'repo_access_summary': {
                    'total_repos': repo_count,
                    'private_repos': private_repo_count,
                    'public_repos': public_repo_count,
                    'pull_repos': pull_repo_count,
                    'triage_repos': triage_repo_count,
                    'push_repos': push_repo_count,
                    'maintain_repos': maintain_repo_count,
                    'admin_repos': admin_repo_count,
                    'write_repos': write_repo_count  # push + maintain + admin
                }
            }
            ledger['tokens'].append(new_token)
            action = "Added"
        
        # Print detailed summary
        repo_details = ", ".join([f"{r['repo_name']}({r['permission']})" for r in repo_access])
        print(f"✅ {action} token for {username} (ID: {member_id}, Role: {role})")
        print(f"   📦 Repos: {repo_count} total ({private_repo_count} private, {public_repo_count} public)")
        print(f"   🔐 Permissions: Pull:{pull_repo_count}, Push:{push_repo_count}, Admin:{admin_repo_count}")
        if repo_details:
            print(f"   📋 Details: {repo_details}")
        else:
            print(f"   📋 No repository access found")
    
    # Save updated ledger
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, 'w') as f:
        yaml.dump(ledger, f, default_flow_style=False, sort_keys=False)
    
    print(f"\n✅ Token ledger updated successfully at {LEDGER_PATH}")


def print_repository_summary():
    """Print a summary of all repositories in the organization"""
    repos = fetch_org_repos()
    
    if not repos:
        print("⚠️  No repositories found")
        return
    
    print(f"\n📦 Repository Summary ({len(repos)} total):")
    print("-" * 80)
    
    for repo in repos:
        repo_name = repo['name']
        repo_private = "🔒 Private" if repo.get('private', False) else "🌐 Public"
        repo_language = repo.get('language') or 'N/A'
        repo_description = repo.get('description') or 'No description'
        repo_description = repo_description[:50] if repo_description else 'No description'
        
        print(f"  • {repo_name:30s} {repo_private:12s} | Language: {repo_language:10s} | {repo_description}")
    
    print("-" * 80)


def main():
    """Main function to orchestrate the member fetch and ledger update"""
    
    if not GITHUB_ORG_NAME or not GITHUB_PAT_TOKEN:
        print("❌ Error: ORG_NAME and PAT_TOKEN must be set in .env file")
        return
    
    print(f"🔍 Fetching members from organization: {GITHUB_ORG_NAME}\n")
    
    # Print repository summary first
    print_repository_summary()
    
    # Fetch all members
    members = fetch_org_members()
    
    if not members:
        print("\n⚠️  No members found or error occurred")
        return
    
    print(f"\n📋 Found {len(members)} member(s)\n")
    
    # Update token ledger with member information
    update_token_ledger(members)


if __name__ == '__main__':
    main()

