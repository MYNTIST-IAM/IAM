# GitHub Actions Setup Guide

## Overview

The survivability scoring bot now runs automatically every 6 hours via GitHub Actions. It:
- ✅ Calculates scores for all tokens
- ✅ Maintains score history (max 7 entries per token)
- ✅ Updates the token ledger
- ✅ Generates reports
- ✅ Commits changes back to the repository

## Schedule

The workflow runs:
- **Every hour**: At the start of every hour (00:00, 01:00, 02:00, etc.)
- **Manually**: You can trigger it anytime from GitHub Actions UI

## Setup Steps

### 1. Add GitHub Secrets

Go to your repository on GitHub:
```
Settings → Secrets and variables → Actions → New repository secret
```

Add these secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `ORG_NAME` | `MYNTIST-IAM` | Your GitHub organization name |
| `PAT_TOKEN` | `ghp_xxxxx...` | Your Personal Access Token |

**Creating a PAT Token:**
1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with these scopes:
   - ✅ `read:org` - Read organization membership
   - ✅ `admin:org` - Read member roles (if admin)
   - ✅ `repo` - Full repository access (for commits)
3. Copy the token and add it as `PAT_TOKEN` secret

### 2. Enable GitHub Actions

Ensure GitHub Actions is enabled:
```
Settings → Actions → General → Actions permissions
→ Select "Allow all actions and reusable workflows"
```

### 3. Enable Workflow Permissions

Give the workflow write permissions:
```
Settings → Actions → General → Workflow permissions
→ Select "Read and write permissions"
→ Check "Allow GitHub Actions to create and approve pull requests"
```

### 4. Push Your Code

```bash
git add .
git commit -m "Setup survivability IAM system with automated scoring"
git push origin main
```

### 5. Manual First Run (Optional)

Test the workflow manually before waiting 6 hours:

1. Go to **Actions** tab in your repository
2. Click on **"Survivability Scoring and Alerts"** workflow
3. Click **"Run workflow"** dropdown
4. Click **"Run workflow"** button

## What Happens Every Hour

```
1. GitHub Actions triggers workflow
   ↓
2. Checks out your repository
   ↓
3. Installs Python dependencies
   ↓
4. Runs survivability_scoring.py
   ↓
5. Updates token-ledger.yml with new scores
   ↓
6. Generates reports (JSON + Markdown)
   ↓
7. Commits and pushes changes back to repo
   ↓
8. You can see the updated scores in your repo
```

## Score History Feature

### How It Works

Each token now has a `score_history` field that stores the last 7 scores:

```yaml
tokens:
  - token_id: 'abc123'
    owner: 'user1'
    survivability_score: 0.85
    score_history:
      - timestamp: '2025-10-14T00:00:00'
        score: 0.80
      - timestamp: '2025-10-14T06:00:00'
        score: 0.82
      - timestamp: '2025-10-14T12:00:00'
        score: 0.85
    # ... max 7 entries
```

### Why 7 Entries?

- Running every hour = 24 times per day
- 7 entries = ~7 hours of history
- Perfect for showing short-term trends in graphs

### Viewing History

**In YAML (token-ledger.yml):**
Each token has a `score_history` array with timestamps

**In JSON (reports/score_history.json):**
Complete history for all tokens in JSON format (ready for graphing)

**In Markdown (reports/token_health_report.md):**
Shows trend like: `0.80 → 0.82 → 0.85`

## Monitoring

### View Workflow Runs

1. Go to **Actions** tab
2. See all past runs and their status
3. Click on any run to see detailed logs

### Check Automated Commits

Look for commits with message:
```
📊 Update survivability scores [automated]
```

These are created by GitHub Actions bot every hour.

## Troubleshooting

### Workflow Failed - "Permission denied"

**Solution:** Enable write permissions (see step 3 above)

### Workflow Failed - "Invalid credentials"

**Solution:** Check your `PAT_TOKEN` secret is correct and has right scopes

### No commits being pushed

**Solution:** Scores might not have changed. Check workflow logs to verify script ran successfully.

### Score history not appearing

**Solution:** Run the script at least once. First run initializes the `score_history` field.

## Testing Locally

Before pushing, test locally:

```bash
# Make sure you have .env file
cp .env_example .env
# Edit .env with your credentials

# Run the scoring bot
python scripts/survivability_scoring.py

# Check the output
cat reports/token_health_report.md
cat reports/score_history.json

# Verify token ledger was updated
cat security/token-ledger.yml
```

## Next Steps

Once this is running:
- Monitor the score trends in your reports
- Build a dashboard to visualize `score_history.json`
- Add Slack/Teams notifications for critical scores
- Implement auto-healing for degrading tokens

## Cron Schedule Reference

Current: `0 * * * *` = Every hour

To change frequency:
- Every 30 minutes: `*/30 * * * *`
- Every 3 hours: `0 */3 * * *`
- Every 6 hours: `0 */6 * * *`
- Every 12 hours: `0 */12 * * *`
- Daily at midnight: `0 0 * * *`
- Twice daily (00:00, 12:00): `0 0,12 * * *`

