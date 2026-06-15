# CreatorPulse MVP Mock Data

This folder contains the first executable slice of the MVP data plan.

It generates one unified mock dataset for all current UI pages instead of page-specific hardcoded data.

## What It Generates

- 1 creator
- 3 platforms: Douyin, Bilibili, Xiaohongshu
- 27 videos, 9 per platform
- 1 latest metric snapshot per video
- 5 traffic source rows per video
- 7 creator trend snapshots
- 1 audience profile snapshot
- 10 topic trend snapshots
- 20-30 rule-based insights
- 6 page-level ViewModels

## Files

| File | Purpose |
|---|---|
| `generate_mock.py` | Generates the complete MVP mock dataset |
| `validate_mock.py` | Validates count, formula, consistency, Insight, and ViewModel rules |
| `data/creatorpulse_mvp_mock.json` | Generated dataset consumed by future Flask/Vue work |

## Run

```powershell
python mvp_mock\generate_mock.py
python mvp_mock\validate_mock.py
```

Expected validation output:

```text
MVP mock validation passed
```

## Current Design

The generator is deterministic through `RANDOM_SEED = 20260614`, so frontend and API development can rely on stable data.

All Insight records are generated with the first MVP strategy:

```text
rules + copy templates
```

No AI-generated Insight copy is used in this phase.

## Next Integration Step

The Flask mock API has been added under `api/`. It reads `data/creatorpulse_mvp_mock.json` and exposes:

```text
GET /api/creators/demo/dashboard/growth
GET /api/creators/demo/fans
GET /api/creators/demo/videos
GET /api/creators/demo/distribution
GET /api/creators/demo/opportunities
GET /api/creators/demo/profile
```

Run API contract tests:

```powershell
python api\tests\test_mock_api.py
```

Run the local API server:

```powershell
python api\app.py
```

Then open:

```text
http://127.0.0.1:5000/api/health
http://127.0.0.1:5000/api/creators/demo/dashboard/growth
```

The next product step is Vue integration: consume these six page ViewModels and replace static HTML data with API-driven rendering.
