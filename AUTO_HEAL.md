# Auto-Heal Local Testing Guide

This guide shows how to test the auto-heal mechanism locally using your workstation, without GitHub Actions.

Notes:
- All enforcement is simulated locally. The scripts update the ledger (`security/token-ledger.yml`) but do not call live GitHub APIs to change org state.
- You can run either the end-to-end flow (detect → manifest → apply) or apply-only with a manual manifest.

---

## Prerequisites

- Python 3.11+
- macOS/Linux terminal
- Optional: virtualenv

```bash
cd /Users/dev/Documents/Usman/IAM/IAM
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

---

## Option A: Full Pipeline (Detect → Manifest → Apply)

1) Ensure a health report exists (or generate one)
```bash
python scripts/survivability_scoring.py
# Outputs reports/token_health.json
```

2) Make detection permissive for testing (temporary)

Edit `security/autoheal-policy.yml` to guarantee at least one candidate. For a quick local test, temporarily lower the thresholds:

```yaml
risk:
  critical_threshold: 0.3   # treat ≤0.25 as critical
acceptance:
  min_critical_count_in_last_n: 1
  min_days_since_last_used: 0
```

3) Run detection (writes manifests and marks pending_action)
```bash
python scripts/auto_heal.py
```
Expected output (example):
```json
{
  "manifests": ["ops/autoheal/20251027/52085750.yml"],
  "count": 1
}
```

4) Inspect generated manifests and ledger changes
```bash
ls -R ops/autoheal
cat ops/autoheal/*/*.yml
```

5) Apply manifests (simulated enforcement → ledger updates)
```bash
python scripts/apply_autoheal.py
```
Verify changes (role/state/scope updated, audit trail appended):
```bash
git --no-pager diff -- security/token-ledger.yml
```

6) Optional: Preview Slack digest (includes pending proposals if any)
```bash
# Create .env with SLACK_WEBHOOK_URL to actually send; otherwise it will print a skip message
python scripts/send_alerts.py
```

7) Cleanup (revert temporary policy and ledger changes)
```bash
# Remove generated manifests
rm -rf ops/autoheal/*
# Revert policy and ledger to last committed state
git checkout -- security/autoheal-policy.yml security/token-ledger.yml
```

---

## Option B: Apply-Only (Manual Manifest)

1) Create a minimal manifest for an existing token (replace token_id/owner as needed)
```bash
TODAY=$(date +%Y%m%d)
mkdir -p "ops/autoheal/$TODAY"
cat > "ops/autoheal/$TODAY/52085750.yml" <<'YAML'
token_id: '52085750'
owner: 'HamzaMasood7'
entity_type: 'user'
current_state:
  role: admin
  state: active
  scope: admin:org, repo, workflow, write:packages
proposed_action:
  type: org_role_change
  target_role: member
reason: 'local test'
proposed_at: '2025-10-27T00:00:00'
YAML
```

2) Apply the manifest and verify ledger updates
```bash
python scripts/apply_autoheal.py
git --no-pager diff -- security/token-ledger.yml
```

3) Cleanup
```bash
rm -rf ops/autoheal/*
git checkout -- security/token-ledger.yml
```

---

## What Gets Changed (Simulated Actions)

- `org_role_change`: updates the token's `role` to `target_role`.
- `revoke_org_access`: sets `state` to `revoked`.
- `scope_reduction`: replaces `scope` with `target_scopes`.
- All applications append an `applied` entry to the token's `audit_trail` and clear `pending_action`.

---

## Troubleshooting

- No report found
```bash
# Run scoring to generate reports/token_health.json
python scripts/survivability_scoring.py
```

- No candidates detected
```bash
# Loosen policy temporarily
echo "Edit security/autoheal-policy.yml (critical_threshold ↓, min_critical_count_in_last_n → 1)"
```

- Nothing changes after apply
```bash
# Ensure a manifest exists under ops/autoheal/YYYYMMDD/
ls -R ops/autoheal
# Inspect manifest content matches script expectations (type/role/scopes)
cat ops/autoheal/*/*.yml
```

- Restore to clean state
```bash
rm -rf ops/autoheal/*
git checkout -- security/autoheal-policy.yml security/token-ledger.yml
```

---

## Reference

- Detector: `scripts/auto_heal.py`
- Apply: `scripts/apply_autoheal.py`
- Policy: `security/autoheal-policy.yml`
- Ledger: `security/token-ledger.yml`
- Reports: `reports/token_health.json`