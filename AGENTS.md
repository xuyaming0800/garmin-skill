# Repository guidance

This repository contains the repo-local `garmin-cn-analysis` Skill. Keep Garmin access read-only unless the user separately requests and authorizes a mutation workflow.

## Commands

- Install: `python3 -m pip install -r requirements.txt`
- Fetch: `python3 .agents/skills/garmin-cn-analysis/scripts/garmin_fetch.py --days 28`
- Test: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- Validate Skill: `python3 /root/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/garmin-cn-analysis`

Never commit Garmin tokens, passwords, raw location data, or generated health-data artifacts. Do not print secret values in logs.
