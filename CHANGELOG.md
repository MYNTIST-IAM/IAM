# Changelog

## Latest Updates

### ✅ Alerting System Added

**Date:** 2025-10-16

#### New Features

1. **Slack Integration**
   - Added `SLACK_WEBHOOK_URL` environment variable
   - Real-time notifications to Slack channel
   - Daily digest summary with health metrics

2. **Alert Script** (`scripts/send_alerts.py`)
   - Monitors token health scores
   - Triggers alerts based on thresholds:
     - 🚨 Critical: Score < 0.2
     - ⚠️ Warning: Score < 0.5
     - ✅ Recovery: Score ≥ 0.8
   - Logs all alerts to `logs/alerts.log`

3. **GitHub Actions Integration**
   - Added alert step to workflow
   - Runs after survivability scoring
   - Commits alert logs to repository

#### Files Added
- `scripts/send_alerts.py` - Alert processing and Slack notification
- `logs/alerts.log` - Alert history log
- `ALERTING_GUIDE.md` - Complete alerting documentation

#### Files Modified
- `.env_example` - Added `SLACK_WEBHOOK_URL`
- `.github/workflows/alerts.yml` - Added alert step, now commits logs/
- `.gitignore` - Allow `logs/alerts.log` to be tracked

#### Environment Variables
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

#### GitHub Secrets Required
- `ORG_NAME` - GitHub organization name
- `PAT_TOKEN` - Personal Access Token
- `SLACK_WEBHOOK_URL` - Slack webhook URL

---

### ✅ Updated Workflow Schedule

**Changes:**
- Changed from hourly to **daily execution** (runs at midnight UTC)
- Cron: `0 0 * * *`

---

### ✅ Complete Workflow

The automated workflow now runs daily with these steps:

1. **Fetch GitHub Members** - Sync organization members
2. **Run Survivability Scoring** - Calculate health scores
3. **Send Alerts** - Process alerts and notify Slack
4. **Commit Changes** - Push updates to repository

---

### ✅ Environment Variable Changes

**Updated naming convention:**
- `GITHUB_ORG_NAME` → `ORG_NAME`
- `GITHUB_PAT_TOKEN` → `PAT_TOKEN`

All scripts and documentation updated accordingly.

---

## Previous Updates

### Initial Release

**Features:**
- Token ledger system
- Survivability scoring bot
- GitHub member fetcher
- Score history tracking (max 7 entries)
- Automated GitHub Actions workflow
- Comprehensive documentation

**Files:**
- `security/token-ledger.yml`
- `scripts/survivability_scoring.py`
- `scripts/fetch_github_members.py`
- `.github/workflows/alerts.yml`
- Documentation files (README, SETUP_GUIDE, etc.)

---

## Coming Soon

### Phase 2 Enhancements
- [ ] Auto-healing mechanisms (token rotation/revocation)
- [ ] Dashboard for visualizing trends
- [ ] Agent ledger tracking
- [ ] Product dependency mapping
- [ ] Enhanced permission usage tracking
- [ ] Scope drift detection
- [ ] Multi-channel notifications (Email, Teams, PagerDuty)

