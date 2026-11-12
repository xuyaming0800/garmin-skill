# Codex Cloud setup

## Environment

Use Python 3.12 or newer. Configure the Codex Cloud environment setup command:

```bash
python3 -m pip install -r requirements.txt
```

Allow outbound HTTPS to the Garmin China authentication and API hosts used by the client, at minimum `sso.garmin.cn`, `connect.garmin.cn`, `connectapi.garmin.cn`, and `diauth.garmin.cn`. Garmin may add or redirect hosts; keep the allowlist narrow and update it only from observed authentication failures.

## Secrets

Preferred Cloud setup:

- `GARMIN_TOKENS_JSON`: reusable token JSON bootstrapped on a trusted local machine.
- Do not store generated artifacts or token JSON in Git.

Fallback setup:

- `GARMIN_EMAIL`
- `GARMIN_PASSWORD`

Password login can require MFA and is therefore less reliable in a non-interactive Cloud task. `GARMIN_MFA_CODE` is accepted for a single run only; do not preserve a one-time code as a long-lived secret.

To bootstrap locally without placing a password in shell history, run:

```bash
export GARMIN_TOKEN_STORE=".garmin-tokens"
python3 .agents/skills/garmin-cn-analysis/scripts/garmin_fetch.py --interactive-auth --days 1
```

Enter the email, password, and MFA code when prompted. Copy the resulting `.garmin-tokens/garmin_tokens.json` content into the Cloud secret `GARMIN_TOKENS_JSON`, then delete unnecessary local copies. A Cloud task cannot update the stored secret when Garmin rotates a token, so repeat this bootstrap if token restoration eventually fails.

Secrets exposed to a Cloud environment may be readable by code running in that environment. Use a dedicated environment, keep network access restricted, rotate credentials/tokens if exposure is suspected, and revoke Garmin sessions from account security settings when needed.

## Run

Invoke the Skill in a Codex task, for example:

```text
Use $garmin-cn-analysis to analyze my last 28 days. Focus on whether training load and recovery support a hard workout this week.
```

The evidence files are written under `artifacts/garmin/` and are ignored by Git.
