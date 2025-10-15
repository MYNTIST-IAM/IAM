# Quick Setup Guide

## What We've Built

You now have a **Survivability IAM System** that:

1. ✅ **Fetches GitHub organization members** via API
2. ✅ **Creates token entries** using their GitHub user ID
3. ✅ **Tracks roles** (admin/member) for each user
4. ✅ **Calculates survivability scores** based on mathematical formulas
5. ✅ **Generates reports** in JSON and Markdown formats

## Files Created

### Core Scripts
- `scripts/fetch_github_members.py` - Fetches members from GitHub API and populates token ledger
- `scripts/survivability_scoring.py` - Calculates health scores for all tokens

### Configuration
- `.env_example` - Template for environment variables
- `requirements.txt` - Python dependencies
- `.gitignore` - Prevents committing sensitive files

### Data
- `security/token-ledger.yml` - Central token registry with 3 example tokens

### Workflows
- `.github/workflows/alerts.yml` - GitHub Actions for automation

## How to Use

### Step 1: Setup Environment

```bash
# Install dependencies
pip install -r requirements.txt

# Create your .env file
cp .env_example .env

# Edit .env and add your GitHub PAT token
nano .env
```

### Step 2: Fetch GitHub Members

```bash
python scripts/fetch_github_members.py
```

**What it does:**
- Calls `https://api.github.com/orgs/MYNTIST-IAM/members`
- For each member, calls `https://api.github.com/orgs/MYNTIST-IAM/memberships/{username}`
- Extracts: `id`, `login`, `role`, `state`
- Creates a token entry in `security/token-ledger.yml` with:
  - `token_id` = GitHub user ID (e.g., `52085750`)
  - `entity_type` = `'user'`
  - `role` = admin or member
  - `scope` = permissions based on role

**Example Output:**
```
🔍 Fetching members from organization: MYNTIST-IAM
📋 Found 1 member(s)
✅ Added token for HamzaMasood7 (ID: 52085750, Role: admin)
✅ Token ledger updated successfully
```

### Step 3: Calculate Survivability Scores

```bash
python scripts/survivability_scoring.py
```

**What it does:**
- Reads all tokens from `security/token-ledger.yml`
- Calculates survivability score using the formula
- Generates reports in `reports/` folder

**Example Output:**
```
✅ Survivability scoring complete. Reports generated in /reports/
```

### Step 4: View Reports

Check the generated reports:

```bash
# View JSON report
cat reports/token_health.json

# View Markdown report
cat reports/token_health_report.md
```

## Understanding the Token Ledger

After running `fetch_github_members.py`, your token ledger will look like:

```yaml
tokens:
  # Existing service account tokens
  - token_id: 'abc123'
    owner: 'user1'
    entity_type: 'service_account'
    role: 'ci_cd'
    ...
  
  # GitHub user tokens (auto-added)
  - token_id: '52085750'           # GitHub user ID
    owner: 'HamzaMasood7'           # GitHub username
    entity_type: 'user'             # Indicates this is a user
    role: 'admin'                   # GitHub role
    state: 'active'                 # Membership state
    scope: 'admin:org, repo, workflow, write:packages'
    usage: 'GitHub Organization Access'
    ...
```

## Key Features

### 1. Automatic Member Detection
The system automatically finds all members in your GitHub organization and creates token entries for them.

### 2. Role-Based Scope Assignment
- **Admin users** get: `admin:org, repo, workflow, write:packages`
- **Regular members** get: `read:org, repo`

### 3. Entity Type Tracking
- `entity_type: 'user'` - GitHub organization members
- `entity_type: 'service_account'` - CI/CD, deployment, API tokens

### 4. Survivability Scoring
Each token gets a health score (0-1):
- **0.8-1.0**: Healthy ✅
- **0.5-0.8**: Degrading ⚠️
- **0-0.5**: Critical 🚨

## What's Next?

The scoring bot currently uses placeholder values for:
- `used_permissions` - defaults to 1
- `scope_drift` - defaults to 0.0

In Phase 2, you'll enhance this to:
- Track actual permission usage from GitHub API
- Calculate scope drift by comparing historical data
- Implement auto-healing (revoke/rotate tokens)
- Add Slack/Teams notifications

## Troubleshooting

### "No members found"
- Check your `PAT_TOKEN` in `.env`
- Ensure your token has `read:org` scope
- Verify the `ORG_NAME` is correct

### "Error fetching role"
- You need admin access to see member roles
- Ensure your PAT has `admin:org` scope (or at least `read:org`)

### Import errors
- Make sure you installed dependencies: `pip install -r requirements.txt`
- Use Python 3.10 or higher

## Security Reminders

🔒 **Never commit:**
- `.env` file (contains your PAT token)
- Actual token values in the ledger
- GitHub secrets

✅ **Always:**
- Use masked/hashed token IDs
- Keep `.env` in `.gitignore`
- Use GitHub Secrets for CI/CD workflows

