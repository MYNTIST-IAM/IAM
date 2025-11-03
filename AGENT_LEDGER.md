# Agent Ledger Documentation

## Overview

The Agent Ledger system tracks AI and automated agents that interact with repositories or APIs. It mirrors the token ledger structure and follows the same survivability scoring mechanism.

## Purpose

- Track all AI/automated agents (e.g., GitHub Actions workflows, CI/CD bots, automation scripts)
- Link each agent to an associated token
- Calculate survivability scores using the same mechanism as tokens
- Monitor agent health and trigger remediation when needed

## Agent Ledger Schema

Each agent in `agents/agent-ledger.yml` contains:

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | String | Unique identifier (e.g., "agent-alerts") |
| `agent_name` | String | Human-readable name from workflow |
| `associated_token_id` | String | **Required** - Links to token in `security/token-ledger.yml` |
| `purpose` | String | Description of what the agent does |
| `interaction_scope` | String | Scope of interactions (same format as token scope, e.g., "read:org, repo, workflow") |
| `survivability_score` | Float | Calculated by scoring bot (0-2.0) |
| `score_history` | List | Last 7 score entries with timestamps |
| `last_scored` | DateTime | ISO timestamp of last scoring |
| `audit_trail` | List | Audit entries for agent actions |
| `state` | String | Status (active/inactive/pending) |
| `created_at` | DateTime | ISO timestamp when agent was created |
| `last_activity` | DateTime | ISO timestamp of last activity |
| `workflow_file` | String | Path to workflow file (e.g., ".github/workflows/alerts.yml") |

### Example Agent Entry

```yaml
agents:
  - agent_id: "agent-alerts"
    agent_name: "Survivability Scoring and Alerts"
    associated_token_id: "abc123"
    purpose: "Survivability Scoring and Alerts (Automated scoring and notifications)"
    interaction_scope: "contents: write, pull-requests: write, issues: write"
    survivability_score: 0.75
    score_history:
      - timestamp: "2025-11-02T02:06:58.323203"
        score: 0.75
      - timestamp: "2025-11-01T02:04:03.861851"
        score: 0.72
    last_scored: "2025-11-02T02:06:58.323208"
    audit_trail: []
    state: "active"
    created_at: "2025-11-02T02:00:00.000000"
    last_activity: "2025-11-02T02:00:00.000000"
    workflow_file: ".github/workflows/alerts.yml"
```

## Agent Detection

Agents are automatically detected from GitHub Actions workflows:

```bash
python scripts/detect_agents.py
```

### Detection Process

1. Scans `.github/workflows/` directory for `.yml` and `.yaml` files
2. Extracts workflow metadata:
   - Workflow name from `name` field
   - Permissions from `permissions` section
   - Job names from `jobs` section
3. Determines `interaction_scope`:
   - Parses workflow permissions
   - Maps to token scope format (e.g., "read:org, repo, workflow")
4. Links to associated token:
   - Attempts to match workflow by name/usage patterns
   - Falls back to first service account token
   - Requires token to exist in token ledger

### Manual Agent Registration

If you need to manually register an agent, edit `agents/agent-ledger.yml`:

```yaml
agents:
  - agent_id: "agent-custom"
    agent_name: "Custom Agent"
    associated_token_id: "your-token-id"
    purpose: "Custom automation task"
    interaction_scope: "read:org, repo"
    survivability_score: 0.0
    score_history: []
    last_scored: null
    audit_trail: []
    state: "active"
    created_at: "2025-11-02T00:00:00"
    last_activity: "2025-11-02T00:00:00"
```

## Scoring Mechanism

Agents use the **same scoring formula** as tokens:

```
S = base_score × role_multiplier × repo_multiplier × time_factor × audit_factor
```

### Scoring Process

1. Uses agent's `interaction_scope` instead of token `scope`
2. References associated token for context:
   - Uses token's role_multiplier (if user/admin)
   - Uses token's repo_multiplier (if available)
   - Uses token's time_factor and audit_factor
3. Calculates score and updates `score_history` (max 7 entries)
4. Generates health reports:
   - `reports/agent_health.json`
   - `reports/agent_health_report.md`

### Health Status

Same thresholds as tokens:

- **Healthy**: S ≥ 0.8
- **Degrading**: 0.5 ≤ S < 0.8
- **Critical**: S < 0.5

## Validation

Validate agent-to-token relationships:

```bash
python scripts/validate_agents.py
```

### Validation Rules

1. **Required Field**: Every agent must have `associated_token_id`
2. **Token Existence**: Referenced token must exist in token ledger
3. **Orphaned Agents**: Detects agents whose tokens have been removed

### Validation Output

```
🔍 Validating 3 agent(s)...

✅ 3 agent(s) validated successfully

✅ All agents validated successfully
```

## Integration with Scoring

The scoring script automatically processes both tokens and agents:

```bash
python scripts/survivability_scoring.py
```

This will:
1. Score all tokens in `security/token-ledger.yml`
2. Score all agents in `agents/agent-ledger.yml`
3. Validate agent-to-token relationships during scoring
4. Generate separate reports for tokens and agents

## Auto-Heal Detection (Future)

Agent auto-heal detection is **currently commented out** in `scripts/auto_heal.py`.

To enable:

1. Uncomment the agent detection code in `scripts/auto_heal.py`
2. Ensure `reports/agent_health.json` exists (generated by scoring)
3. Update policy if needed for agent-specific rules

When enabled, agents with critical scores will:
- Generate remediation manifests
- Link remediation to associated token
- Follow same auto-heal workflow as tokens

## Reports

### Agent Health JSON (`reports/agent_health.json`)

```json
[
  {
    "agent_id": "agent-alerts",
    "agent_name": "Survivability Scoring and Alerts",
    "associated_token_id": "abc123",
    "survivability_score": 0.75,
    "status": "Degrading",
    "score_history": [...],
    "purpose": "Automated scoring and notifications",
    "interaction_scope": "read:org, repo"
  }
]
```

### Agent Health Markdown (`reports/agent_health_report.md`)

Markdown table with agent health metrics and trend visualization.

## Best Practices

1. **Run Detection First**: Always run `detect_agents.py` before scoring
2. **Validate Regularly**: Run `validate_agents.py` to catch orphaned agents
3. **Link Correctly**: Ensure agents are linked to appropriate tokens
4. **Monitor Reports**: Review agent health reports regularly
5. **Update Workflows**: Re-run detection when adding new workflows

## Troubleshooting

### No Agents Detected

- Check that `.github/workflows/` directory exists
- Ensure workflow files have `.yml` or `.yaml` extension
- Verify workflows are valid YAML

### Invalid Token Association

- Run `validate_agents.py` to identify issues
- Ensure token exists in token ledger
- Re-run `detect_agents.py` after adding tokens

### Agents Not Scoring

- Ensure `survivability_scoring.py` runs successfully
- Check that agent ledger exists at `agents/agent-ledger.yml`
- Verify agents have valid `associated_token_id`

## Related Documentation

- [`README.md`](README.md) - Main system documentation
- [`ARCHITECTURE.md`](ARCHITECTURE.md) - System architecture
- [`ENFORCEMENT_GUIDE.md`](ENFORCEMENT_GUIDE.md) - Auto-heal enforcement guide

