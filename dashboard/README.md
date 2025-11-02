# IAM Survivability Dashboard

React dashboard for monitoring IAM token health and survivability scores.

## Setup

```bash
npm install
npm start
```

The app will run on http://localhost:3000

## Data Files

The dashboard reads JSON files from the `public/` folder:
- `token_health.json` - Current token health status
- `score_history.json` - Historical score data for trends

These files are automatically copied from `reports/` when `survivability_scoring.py` runs.

## Features

- Real-time token health monitoring
- Score trend visualization
- Status-based filtering and alerts
- Auto-refresh every 5 minutes

