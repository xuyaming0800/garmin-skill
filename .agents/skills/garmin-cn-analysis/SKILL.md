---
name: garmin-cn-analysis
description: Fetch read-only training and health data from a personal Garmin China account, then analyze training load, recovery, sleep, and trends. Use for Garmin 中国区 or connect.garmin.cn analysis; do not use for writing workouts or changing account data.
---

# Garmin China Analysis

Use the bundled fetcher to create a local, redacted evidence bundle, then analyze that bundle. This integration uses Garmin Connect's unofficial personal-account web interface through `garminconnect`; it is not the approved Garmin Health API.

## Fetch

1. Confirm that the requested date range is clear. Default to 28 days ending today in `Asia/Shanghai`.
2. Run from the repository root:

   ```bash
   python3 .agents/skills/garmin-cn-analysis/scripts/garmin_fetch.py --days 28
   ```

3. Read `artifacts/garmin/analysis-brief.md`, then inspect only the needed sections of `artifacts/garmin/garmin-data.json`.
4. If authentication, MFA, or Cloud setup fails, read [references/cloud-setup.md](references/cloud-setup.md). For data meanings and known limitations, read [references/data-guide.md](references/data-guide.md).

Never print credentials, tokens, cookies, or the value of a secret. Never commit files under `artifacts/` or `.garmin-tokens/`. Keep location redaction enabled unless the user explicitly needs route/location analysis and understands the privacy impact.

## Analyze

Base every conclusion on available fields and distinguish measured values from inference. Prefer comparisons over isolated readings:

- Compare the latest 7 days with the preceding 7 or 21 days where coverage allows.
- Relate activity volume, duration, intensity, and Garmin training load to sleep, resting heart rate, HRV, stress, Body Battery, and training readiness.
- Mention missing days, unsupported device metrics, and endpoint errors before drawing conclusions.
- Treat Garmin scores as device estimates, not diagnoses. Do not give medical diagnoses or tell the user to ignore symptoms or clinician advice.

Return a concise report with: date range and coverage, training summary, recovery/health summary, notable relationships, and practical next steps. Attribute derived insights to Garmin device-sourced data.

This Skill is read-only. Do not call upload, update, schedule, set, add, or delete methods even if the library exposes them. Follow an explicit user request that narrows the analysis; require separate authorization for any future account mutation workflow.
