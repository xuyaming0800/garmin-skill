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

- `GARMIN_USERNAME` (legacy `GARMIN_EMAIL` is also accepted; `GARMIN_USERNAME` takes priority)
- `GARMIN_PASSWORD`

Fresh authentication uses the Garmin username and password, followed by the phone verification code when Garmin requests SMS/MFA. The library handles requesting and submitting verification in the same login session. `GARMIN_MFA_CODE` is accepted for one verification attempt only; do not preserve a one-time code as a long-lived secret. Prefer interactive bootstrap because the code is normally delivered after submitting the credentials.

To bootstrap locally without placing a password in shell history, run:

```bash
python3 .agents/skills/garmin-cn-analysis/scripts/garmin_fetch.py --interactive-auth --auth-only
```

Enter the username, password, and phone verification code when prompted. Password and code input is hidden. Tokens are saved by default to `.garmin-tokens/garmin_tokens.json`; set `GARMIN_TOKEN_STORE` to override the directory. The token file is owner-readable/writable only (`0600`) inside an owner-only directory (`0700`). A save failure is reported as an error. `--auth-only` skips training/health fetching and evidence output.

Later runs restore saved tokens before asking for credentials, including with `--interactive-auth`. If restoration fails authentication, interactive mode asks for missing credentials and then a new code when Garmin requests verification. Network errors and rate limits stop the run. Non-interactive mode reports missing credentials or verification input instead of prompting.

Copy the resulting `.garmin-tokens/garmin_tokens.json` content into the Cloud secret `GARMIN_TOKENS_JSON`, then delete unnecessary local copies. Inline tokens take priority over the local store and stay in memory when successfully restored. A Cloud task cannot update the stored secret when Garmin rotates a token, so repeat this bootstrap if token restoration eventually fails.

Secrets exposed to a Cloud environment may be readable by code running in that environment. Use a dedicated environment, keep network access restricted, rotate credentials/tokens if exposure is suspected, and revoke Garmin sessions from account security settings when needed.

## Run

Invoke the Skill in a Codex task, for example:

```text
Use $garmin-cn-analysis to analyze my last 28 days. Focus on whether training load and recovery support a hard workout this week.
```

The evidence files are written under `artifacts/garmin/` and are ignored by Git.
