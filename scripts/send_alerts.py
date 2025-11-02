import os
import json
import requests
import yaml
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
REPORT_JSON = Path("reports/token_health.json")
ALERT_LOG = Path("logs/alerts.log")
LEDGER_PATH = Path("security/token-ledger.yml")

# Alert thresholds
CRITICAL_THRESHOLD = 0.2
WARNING_THRESHOLD = 0.5
RECOVERY_THRESHOLD = 0.8


def log_alert(message):
    """Log alert to file"""
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(ALERT_LOG, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")


def send_slack_message(blocks, text):
    """Send message to Slack via webhook"""
    if not SLACK_WEBHOOK_URL or SLACK_WEBHOOK_URL == 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL':
        print("⚠️  Slack webhook not configured. Skipping Slack notification.")
        return False
    
    payload = {
        "text": text,
        "blocks": blocks
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("✅ Slack notification sent successfully")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Error sending Slack notification: {e}")
        log_alert(f"ERROR: Failed to send Slack notification - {e}")
        return False


def get_status_emoji(status):
    """Get emoji for status"""
    if status == "Healthy":
        return "✅"
    elif status == "Degrading":
        return "⚠️"  # Warning sign for degrading/warning status
    else:  # Critical
        return "🚨"


def create_alert_message(token):
    """Create alert message for a token based on its score"""
    token_id = token['token_id']
    owner = token['owner']
    score = token['survivability_score']
    status = token['status']
    
    if score < CRITICAL_THRESHOLD:
        message = f"🚨 CRITICAL: Token {token_id} (owner: {owner}) is in critical state with score {score}. Immediate action required!"
        severity = "CRITICAL"
    elif score < WARNING_THRESHOLD:
        message = f"⚠️ WARNING: Token {token_id} (owner: {owner}) is degrading with score {score}. Reduced survivability detected."
        severity = "WARNING"
    elif score >= RECOVERY_THRESHOLD:
        message = f"✅ RECOVERY: Token {token_id} (owner: {owner}) has recovered with score {score}. Token health improved."
        severity = "RECOVERY"
    else:
        return None  # No alert needed for normal status
    
    return {
        "token_id": token_id,
        "owner": owner,
        "score": score,
        "status": status,
        "message": message,
        "severity": severity
    }


def generate_daily_digest(tokens):
    """Generate daily digest summary"""
    total_tokens = len(tokens)
    healthy = sum(1 for t in tokens if t['status'] == 'Healthy')
    degrading = sum(1 for t in tokens if t['status'] == 'Degrading')
    critical = sum(1 for t in tokens if t['status'] == 'Critical')
    
    avg_score = sum(t['survivability_score'] for t in tokens) / total_tokens if total_tokens > 0 else 0
    
    return {
        "total": total_tokens,
        "healthy": healthy,
        "degrading": degrading,
        "critical": critical,
        "avg_score": round(avg_score, 3)
    }


def create_slack_blocks(alerts, digest):
    """Create Slack message blocks"""
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🔐 Token Survivability Report",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Daily Security Status Update*\n_{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}_"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Total Tokens:*\n{digest['total']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Average Score:*\n{digest['avg_score']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"✅ *Healthy:*\n{digest['healthy']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"⚠️ *Degrading:*\n{digest['degrading']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"🚨 *Critical:*\n{digest['critical']}"
                }
            ]
        }
    ]
    
    # Add alerts section if there are any
    if alerts:
        blocks.append({
            "type": "divider"
        })
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*⚡ Alerts ({len(alerts)}):*"
            }
        })
        
        for alert in alerts:
            emoji = get_status_emoji(alert['status'])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{alert['severity']}*\n"
                            f"Token: `{alert['token_id']}` | Owner: `{alert['owner']}`\n"
                            f"Score: *{alert['score']}* | Status: {alert['status']}"
                }
            })
    else:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "✨ *No alerts* - All tokens are operating normally"
            }
        })
    
    blocks.append({
        "type": "divider"
    })
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "🤖 Automated by Survivability IAM System"
            }
        ]
    })
    
    return blocks


def main():
    """Main function to process alerts and send notifications"""
    
    # Check if report exists
    if not REPORT_JSON.exists():
        print("❌ No report found. Run survivability_scoring.py first.")
        return
    
    # Load token health report
    with open(REPORT_JSON, 'r') as f:
        tokens = json.load(f)
    
    print(f"📊 Processing {len(tokens)} tokens for alerts...")
    
    # Generate alerts
    alerts = []
    for token in tokens:
        alert = create_alert_message(token)
        if alert:
            alerts.append(alert)
            log_alert(alert['message'])
            print(f"  {alert['severity']}: {token['token_id']} - Score: {token['survivability_score']}")
    
    if not alerts:
        print("✅ No alerts triggered - all tokens are in acceptable state")
    
    # Try to surface pending auto-heal proposals
    pending = []
    try:
        with open(LEDGER_PATH, 'r') as f:
            ledger = yaml.safe_load(f)
        for t in ledger.get('tokens', []):
            pa = t.get('pending_action')
            if isinstance(pa, dict) and pa.get('type'):
                pending.append({
                    'token_id': t.get('token_id'),
                    'owner': t.get('owner'),
                    'action': pa.get('type'),
                    'pr': pa.get('pr_number')
                })
    except Exception:
        pass

    # Generate daily digest
    digest = generate_daily_digest(tokens)
    
    # Log digest
    digest_msg = f"DIGEST: Total={digest['total']}, Healthy={digest['healthy']}, Degrading={digest['degrading']}, Critical={digest['critical']}, AvgScore={digest['avg_score']}"
    log_alert(digest_msg)
    
    # Send to Slack
    blocks = create_slack_blocks(alerts, digest)
    if pending:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*🛠 Pending Auto‑Heal Proposals:*"}
        })
        for p in pending[:10]:
            pr_text = f"PR #{p['pr']}" if p.get('pr') else "PR pending"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Token `{p['token_id']}` · Owner `{p['owner']}` · Action `{p['action']}` · {pr_text}"
                }
            })
    summary_text = f"Token Health: {digest['healthy']} healthy, {digest['degrading']} degrading, {digest['critical']} critical"
    
    send_slack_message(blocks, summary_text)
    
    print(f"\n✅ Alert processing complete")
    print(f"   📝 Alerts logged to: {ALERT_LOG}")
    print(f"   🔔 Total alerts: {len(alerts)}")
    print(f"   📊 Digest: {digest}")


if __name__ == '__main__':
    main()

