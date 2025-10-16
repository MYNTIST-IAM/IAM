# Alerting System Guide

## Overview

The Survivability IAM System includes an automated alerting system that monitors token health and sends notifications to Slack.

## How It Works

The `send_alerts.py` script runs automatically after scoring and:
1. ✅ Analyzes token health from reports
2. ✅ Triggers alerts based on thresholds
3. ✅ Logs all alerts to `logs/alerts.log`
4. ✅ Sends daily digest to Slack channel

## Alert Thresholds

| Threshold | Score Range | Severity | Action |
|-----------|-------------|----------|--------|
| **Critical** | S < 0.2 | 🚨 CRITICAL | Immediate action required |
| **Warning** | 0.2 ≤ S < 0.5 | ⚠️ WARNING | Token is degrading |
| **Recovery** | S ≥ 0.8 | ✅ RECOVERY | Token health improved |
| **Normal** | 0.5 ≤ S < 0.8 | ℹ️ INFO | No alert needed |

## Alert Types

### 1. Critical Alert
**Trigger:** Score < 0.2  
**Message:** `"🚨 CRITICAL: Token {id} (owner: {owner}) is in critical state with score {score}. Immediate action required!"`

**Example:**
```
🚨 CRITICAL: Token def456 (owner: user2) is in critical state with score 0.15. Immediate action required!
```

### 2. Warning Alert
**Trigger:** Score < 0.5  
**Message:** `"⚠️ WARNING: Token {id} (owner: {owner}) is degrading with score {score}. Reduced survivability detected."`

**Example:**
```
⚠️ WARNING: Token 52085750 (owner: HamzaMasood7) is degrading with score 0.25. Reduced survivability detected.
```

### 3. Recovery Alert
**Trigger:** Score ≥ 0.8  
**Message:** `"✅ RECOVERY: Token {id} (owner: {owner}) has recovered with score {score}. Token health improved."`

**Example:**
```
✅ RECOVERY: Token abc123 (owner: user1) has recovered with score 1.0. Token health improved.
```

## Slack Integration

### Setup Slack Webhook

1. Go to your Slack workspace
2. Create an incoming webhook:
   - Visit: https://api.slack.com/messaging/webhooks
   - Click "Create New App" → "From scratch"
   - Add "Incoming Webhooks" feature
   - Activate and create webhook for your channel (e.g., #security-status)
3. Copy the webhook URL (format: `https://hooks.slack.com/services/XXX/YYY/ZZZ`)
4. Add to your `.env` file:
   ```
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
   ```
5. Add to GitHub Secrets:
   - Settings → Secrets → Actions → New repository secret
   - Name: `SLACK_WEBHOOK_URL`
   - Value: Your webhook URL

### Slack Message Format

The daily digest includes:

**Header:**
- 🔐 Token Survivability Report
- Timestamp

**Summary Stats:**
- Total Tokens
- Average Score
- ✅ Healthy count
- ⚠️ Degrading count
- 🚨 Critical count

**Alerts Section:**
Each alert shows:
- Severity emoji and level
- Token ID and Owner
- Current Score and Status

**Example Message:**
```
🔐 Token Survivability Report
Daily Security Status Update
2025-10-16 06:18:08 UTC

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Tokens: 4          Average Score: 0.688
✅ Healthy: 2            ⚠️ Degrading: 1
🚨 Critical: 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ Alerts (3):

⚠️ WARNING
Token: 52085750 | Owner: HamzaMasood7
Score: 0.25 | Status: Degrading

✅ RECOVERY
Token: abc123 | Owner: user1
Score: 1.0 | Status: Healthy

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 Automated by Survivability IAM System
```

## Alert Logging

All alerts are logged to `logs/alerts.log` with timestamps.

**Log Format:**
```
[YYYY-MM-DD HH:MM:SS] {severity} {message}
```

**Example Log:**
```
[2025-10-16 06:18:08] 🚨 CRITICAL: Token def456 (owner: user2) is in critical state with score 0.15. Immediate action required!
[2025-10-16 06:18:08] ⚠️ WARNING: Token 52085750 (owner: HamzaMasood7) is degrading with score 0.25. Reduced survivability detected.
[2025-10-16 06:18:08] ✅ RECOVERY: Token abc123 (owner: user1) has recovered with score 1.0. Token health improved.
[2025-10-16 06:18:08] DIGEST: Total=4, Healthy=2, Degrading=1, Critical=1, AvgScore=0.688
```

## Testing Locally

Test the alerting system:

```bash
# Make sure you've run scoring first
python scripts/survivability_scoring.py

# Run the alert script
python scripts/send_alerts.py

# Check the log
cat logs/alerts.log
```

## GitHub Actions Integration

The workflow runs automatically daily:

```yaml
1. Fetch GitHub members
2. Run survivability scoring bot
3. Send alerts and notifications  ← Alerting step
4. Commit and push changes
```

## Customization

### Adjust Alert Thresholds

Edit `scripts/send_alerts.py`:

```python
# Alert thresholds
CRITICAL_THRESHOLD = 0.2   # Change to 0.15 for stricter critical alerts
WARNING_THRESHOLD = 0.5    # Change to 0.6 for earlier warnings
RECOVERY_THRESHOLD = 0.8   # Change to 0.85 for stricter recovery
```

### Customize Slack Message

Modify the `create_slack_blocks()` function in `scripts/send_alerts.py` to change:
- Message formatting
- Color coding
- Additional fields
- Emoji usage

### Add Email Alerts

Extend `send_alerts.py` to include email notifications:

```python
import smtplib
from email.mime.text import MIMEText

def send_email_alert(alert):
    # Implement email sending logic
    pass
```

## Troubleshooting

### No Slack notifications received

**Check:**
1. `SLACK_WEBHOOK_URL` is set correctly in `.env` or GitHub Secrets
2. Webhook URL is valid and active
3. Slack app has permission to post in the channel
4. Check script output for error messages

### Alerts not triggering

**Check:**
1. Token scores are calculated correctly
2. Thresholds are set appropriately
3. Report file exists at `reports/token_health.json`
4. Run script manually to see debug output

### Log file not created

**Check:**
1. Script has write permissions for `logs/` directory
2. `.gitignore` allows `logs/alerts.log`
3. Run script manually to debug

## Future Enhancements

- [ ] Add support for Microsoft Teams webhooks
- [ ] Implement email alerts
- [ ] Add PagerDuty integration for critical alerts
- [ ] Create alert suppression rules
- [ ] Add alert history dashboard
- [ ] Implement alert acknowledgment system
- [ ] Add custom alert templates per team

## Best Practices

1. **Monitor the #security-status channel** - Act on critical alerts immediately
2. **Review weekly trends** - Look for patterns in degrading tokens
3. **Tune thresholds** - Adjust based on your organization's needs
4. **Test regularly** - Manually trigger alerts to ensure system works
5. **Keep logs** - Archive `alerts.log` for compliance and auditing

## Support

For issues or questions about the alerting system:
- Check `logs/alerts.log` for detailed information
- Review token scores in `reports/token_health_report.md`
- Test locally before investigating GitHub Actions issues

