# Product Ledger Documentation

## Overview

The Product Ledger system tracks products (apps, APIs, assets), maps them to agents and tokens, and calculates aggregate survivability health for dashboard visualization.

## Purpose

- Track all products in the organization
- Link products to their dependencies (agents and tokens)
- Calculate aggregate health from dependency scores
- Provide green/yellow/red status visualization
- Enable dashboard auto-calculation from pre-calculated values

## Product Ledger Schema

Each product in `products/product-ledger.yml` contains:

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | String | Unique identifier (e.g., "product-iam-system") |
| `product_name` | String | Name of the app, API, or asset |
| `responsible_team` | String | Owning team |
| `linked_agents` | List | List of agent IDs used by this product |
| `linked_tokens` | List | List of token IDs used by this product |
| `survivability_health` | Float | Aggregate health score (calculated) |
| `health_status` | String | Green/Yellow/Red status (calculated) |
| `last_calculated` | DateTime | ISO timestamp of last health calculation |
| `created_at` | DateTime | ISO timestamp when product was created |
| `updated_at` | DateTime | ISO timestamp of last update |
| `repo_url` | String | (Optional) GitHub repository URL |
| `repo_id` | String | (Optional) GitHub repository ID |
| `auto_detected` | Boolean | (Optional) Whether product was auto-detected |

### Example Product Entry

```yaml
products:
  - product_id: "product-iam-system"
    product_name: "IAM System"
    responsible_team: "Security Team"
    linked_agents:
      - "agent-alerts"
      - "agent-autoheal-detect"
    linked_tokens:
      - "abc123"
      - "def456"
    survivability_health: 0.75
    health_status: "Yellow"
    last_calculated: "2025-11-03T02:00:00"
    created_at: "2025-11-03T00:00:00"
    updated_at: "2025-11-03T02:00:00"
    auto_detected: true
```

## Product Registration

### Automatic Detection

Products can be automatically detected from GitHub repositories:

```bash
python scripts/detect_products.py
```

**Detection Process:**

1. Fetches all repositories from GitHub organization
2. Creates product entry for each repository
3. Sets `responsible_team` to repository owner
4. **Note**: Products are created without linked agents/tokens (requires manual linking)

**Limitations:**

- Products are auto-detected but require manual linking to agents/tokens
- Only creates products from repositories in the organization
- Requires `PAT_TOKEN` and `ORG_NAME` environment variables

### Manual Registration

Products can be manually added to `products/product-ledger.yml`:

```yaml
products:
  - product_id: "product-custom-api"
    product_name: "Custom API"
    responsible_team: "Engineering Team"
    linked_agents:
      - "agent-custom-workflow"
    linked_tokens:
      - "your-token-id"
    survivability_health: 0.0  # Will be calculated
    health_status: "Unknown"    # Will be calculated
    last_calculated: null
    created_at: "2025-11-03T00:00:00"
    updated_at: "2025-11-03T00:00:00"
```

**Best Practices:**

- Use descriptive `product_id` (e.g., "product-service-name")
- Link all relevant agents and tokens
- Update `responsible_team` to actual team name
- Include repository URL if applicable

## Health Calculation

### Formula

Product health is calculated as the **average of all linked token and agent scores**:

```
survivability_health = (sum(token_scores) + sum(agent_scores)) / (token_count + agent_count)
```

### Status Mapping

- **Green**: health >= 0.8 (Healthy)
- **Yellow**: 0.2 <= health < 0.8 (Degrading)
- **Red**: health < 0.2 (Critical)
- **Unknown**: No dependencies linked

### Calculation Process

1. **Collect Scores**: Gather survivability scores from all linked tokens and agents
2. **Calculate Average**: Sum all scores and divide by total count
3. **Determine Status**: Map score to Green/Yellow/Red
4. **Update Ledger**: Save calculated health and status
5. **Generate Reports**: Create JSON and Markdown reports

### When Health is Calculated

- **Automatic**: After token/agent scoring in `survivability_scoring.py`
- **Manual**: Run `python scripts/calculate_product_health.py`
- **Dashboard**: Uses pre-calculated values from `reports/product_health.json`

## Validation

Validate product-to-agent/token relationships:

```bash
python scripts/validate_products.py
```

### Validation Rules

1. **Dependencies Required**: Every product should have at least one linked token or agent
2. **Agent Existence**: All linked agents must exist in agent ledger
3. **Token Existence**: All linked tokens must exist in token ledger
4. **Orphaned Products**: Detects products whose dependencies have all been removed

### Validation Output

```
🔍 Validating 3 product(s)...

✅ 3 product(s) validated successfully

✅ All products validated successfully
```

## Integration with Scoring

Product health is automatically calculated after token/agent scoring:

```bash
python scripts/survivability_scoring.py
```

This will:
1. Score all tokens
2. Score all agents
3. Calculate product health (aggregate of dependencies)
4. Generate product health reports

## Reports

### Product Health JSON (`reports/product_health.json`)

Pre-calculated values for dashboard consumption:

```json
[
  {
    "product_id": "product-iam-system",
    "product_name": "IAM System",
    "responsible_team": "Security Team",
    "survivability_health": 0.75,
    "health_status": "Yellow",
    "linked_agents_count": 2,
    "linked_tokens_count": 2,
    "dependency_scores": [0.8, 0.7, 0.75, 0.75],
    "missing_dependencies": []
  }
]
```

### Product Health Markdown (`reports/product_health_report.md`)

Human-readable report with status indicators and dependency counts.

## Dashboard Integration

The React dashboard reads pre-calculated product health from `reports/product_health.json`:

1. **Auto-refresh**: Dashboard fetches product health on load
2. **Tab Navigation**: Switch between Token Health and Product Health views
3. **Status Visualization**: Green/Yellow/Red badges for each product
4. **Dependency Display**: Shows linked agents and tokens count

To use the dashboard:

1. Ensure `reports/product_health.json` exists (generated by scoring script)
2. Copy to `dashboard/public/product_health.json`
3. Dashboard will automatically load and display product health

## Best Practices

1. **Link Accurately**: Ensure all relevant agents and tokens are linked
2. **Update Regularly**: Re-run detection after adding new repositories
3. **Validate Often**: Run validation script to catch orphaned products
4. **Monitor Health**: Review product health reports regularly
5. **Team Ownership**: Keep `responsible_team` updated

## Troubleshooting

### Products Not Showing Health

- Ensure products have linked agents or tokens
- Run `python scripts/calculate_product_health.py` manually
- Check that token/agent scores exist in health reports

### Missing Dependencies

- Run `python scripts/validate_products.py` to identify issues
- Ensure all linked agents exist in agent ledger
- Ensure all linked tokens exist in token ledger

### Dashboard Not Showing Products

- Verify `reports/product_health.json` exists
- Copy to `dashboard/public/product_health.json`
- Check browser console for errors

### Health Calculation Errors

- Check that token and agent health reports exist
- Verify product has at least one linked dependency
- Review calculation script logs for errors

## Related Documentation

- [`README.md`](README.md) - Main system documentation
- [`AGENT_LEDGER.md`](AGENT_LEDGER.md) - Agent ledger documentation
- [`ARCHITECTURE.md`](ARCHITECTURE.md) - System architecture

