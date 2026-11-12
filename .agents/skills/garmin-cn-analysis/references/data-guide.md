# Data guide and limits

## Sources

The script uses `garminconnect` with `is_cn=True`, which routes personal-account requests to Garmin China. These web endpoints are unofficial, can change without notice, and may differ by account, device, subscription, and firmware.

Garmin's official Health API is a separate enterprise program requiring approval. It supports consented health data such as steps, heart rate, sleep, stress, Pulse Ox, Body Battery, body composition, and respiration. Replace the personal-account adapter with the official API before using this project for a multi-user or commercial service.

## Evidence sections

- `training.activities`: activity summaries in the requested range.
- `training.activity_load`: per-activity training-load metrics when supported.
- `training.readiness`, `weekly_status`, `current_status`, `load_balance`: Garmin training estimates; unsupported devices may return no data.
- `health.daily_summaries`: daily activity and wellness summaries.
- `health.heart_rate`, `hrv`, `stress`, `body_battery`, `intensity_minutes`, `respiration`, `body_composition`: range series when available.
- `health.sleep`: daily sleep responses for the most recent requested sleep window.
- `errors`: endpoints that failed independently. A partial bundle is still analyzable if coverage is stated.

## Interpretation

Use trends and within-person baselines. Do not compare a user's raw HRV, stress, sleep score, Body Battery, or readiness directly with another person's. Device-derived metrics can be affected by wear time, sensor fit, illness, travel, alcohol, medication, and firmware/algorithm changes.

For China/UTC+8 accounts, prefer GMT epoch fields plus the profile timezone when local sleep timestamp fields conflict. Do not silently repair timestamps without explaining the rule used.

The fetcher strips exact location-like fields and common account identifiers by default. `--include-location` is an explicit privacy opt-in.
