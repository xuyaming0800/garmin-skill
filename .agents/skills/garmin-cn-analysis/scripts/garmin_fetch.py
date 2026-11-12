#!/usr/bin/env python3
"""Fetch a redacted, read-only Garmin China evidence bundle for Codex."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_OUTPUT = Path("artifacts/garmin/garmin-data.json")
DEFAULT_TOKEN_STORE = ".garmin-tokens"
SENSITIVE_KEY = re.compile(
    r"(token|password|cookie|authorization|email|display.?name|profile.?id)",
    re.IGNORECASE,
)
LOCATION_KEY = re.compile(
    r"(latitude|longitude|polyline|geo.?point|start.?location|end.?location|address)",
    re.IGNORECASE,
)


class AuthenticationInputError(RuntimeError):
    """An actionable authentication input error containing no secret values."""


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def date_window(days: int, end: date | None = None) -> tuple[date, date]:
    if not 1 <= days <= 90:
        raise ValueError("days must be between 1 and 90")
    end = end or datetime.now(SHANGHAI).date()
    return end - timedelta(days=days - 1), end


def redact(value: Any, include_location: bool = False) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if SENSITIVE_KEY.search(key_text):
                continue
            if not include_location and LOCATION_KEY.search(key_text):
                continue
            result[key_text] = redact(item, include_location)
        return result
    if isinstance(value, list):
        return [redact(item, include_location) for item in value]
    if isinstance(value, tuple):
        return [redact(item, include_location) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def safe_exception(exc: Exception) -> str:
    message = str(exc)
    message = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted-email]", message)
    message = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [redacted]", message)
    return f"{type(exc).__name__}: {message[:500]}"


def call_section(
    errors: list[dict[str, str]], name: str, fn: Callable[..., Any], *args: Any
) -> Any:
    try:
        return fn(*args)
    except Exception as exc:  # External endpoints vary by account and device.
        errors.append({"section": name, "error": safe_exception(exc)})
        return None


def build_client(interactive_auth: bool = False) -> Any:
    try:
        from garminconnect import Garmin, GarminConnectAuthenticationError
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency. Run: python3 -m pip install -r requirements.txt"
        ) from exc

    username = (os.getenv("GARMIN_USERNAME") or os.getenv("GARMIN_EMAIL") or "").strip()
    password = os.getenv("GARMIN_PASSWORD")
    token_json = os.getenv("GARMIN_TOKENS_JSON")
    token_store = str(
        Path(os.getenv("GARMIN_TOKEN_STORE") or DEFAULT_TOKEN_STORE).expanduser()
    )
    mfa_code = (os.getenv("GARMIN_MFA_CODE") or "").strip()

    def prompt_mfa() -> str:
        nonlocal mfa_code
        if mfa_code:
            code, mfa_code = mfa_code, ""
        elif interactive_auth:
            code = getpass.getpass(
                "Garmin phone verification code (SMS/MFA): "
            ).strip()
        else:
            raise AuthenticationInputError(
                "Garmin requested a phone verification code. Use --interactive-auth "
                "or provide GARMIN_MFA_CODE for this run only."
            )
        if not code:
            raise AuthenticationInputError("Garmin phone verification code must not be empty.")
        return code

    try:
        # Restore first so a valid token never requires credentials or another SMS.
        client = Garmin(is_cn=True, retry_attempts=3)
        try:
            client.login(token_json or token_store)
        except GarminConnectAuthenticationError:
            if interactive_auth:
                username = username or input("Garmin username: ").strip()
                password = password or getpass.getpass("Garmin password: ")
            if not username or not password:
                raise AuthenticationInputError(
                    "No usable Garmin token. Run --interactive-auth, or set "
                    "GARMIN_USERNAME (GARMIN_EMAIL is also supported) and GARMIN_PASSWORD."
                )
            client = Garmin(
                email=username,  # The library names its username argument 'email'.
                password=password,
                is_cn=True,
                prompt_mfa=prompt_mfa,
                return_on_mfa=False,
                retry_attempts=3,
            )
            client.login(token_store)
        else:
            # Inline Cloud secrets stay in memory; local stores retain refreshed tokens.
            if token_json:
                return client
    except AuthenticationInputError:
        raise
    except Exception as exc:
        # Authentication exceptions may include credentials or token response bodies.
        raise RuntimeError(
            f"Garmin authentication failed ({type(exc).__name__}). Check the username, "
            "password and phone verification code; use --interactive-auth or provide "
            "GARMIN_MFA_CODE when verification is required. If rate limited, wait before retrying."
        ) from None

    # login() suppresses persistence errors; explicitly save so auth-only cannot report
    # success when the reusable token was not actually written. The library enforces
    # owner-only permissions and atomic writes.
    try:
        client.client.dump(token_store)
    except Exception as exc:
        raise RuntimeError(
            f"Garmin authenticated, but token saving failed ({type(exc).__name__}). "
            "Check GARMIN_TOKEN_STORE permissions."
        ) from None
    return client


def collect(client: Any, start: date, end: date, sleep_days: int) -> dict[str, Any]:
    start_text, end_text = start.isoformat(), end.isoformat()
    errors: list[dict[str, str]] = []
    sleep_start = max(start, end - timedelta(days=sleep_days - 1))

    sleep: dict[str, Any] = {}
    cursor = sleep_start
    while cursor <= end:
        day = cursor.isoformat()
        sleep[day] = call_section(errors, f"sleep.{day}", client.get_daily_sleep, day)
        cursor += timedelta(days=1)

    return {
        "metadata": {
            "source": "Garmin Connect China (unofficial personal-account interface)",
            "region": "garmin.cn",
            "start_date": start_text,
            "end_date": end_text,
            "sleep_start_date": sleep_start.isoformat(),
            "fetched_at": datetime.now(SHANGHAI).isoformat(),
            "attribution": "Insights derived from Garmin device-sourced data.",
        },
        "training": {
            "activities": call_section(
                errors, "activities", client.get_activities_by_date, start_text, end_text
            ),
            "activity_load": call_section(
                errors,
                "activity_load",
                client.get_training_load_activities,
                start_text,
                end_text,
            ),
            "readiness": call_section(
                errors,
                "training_readiness",
                client.get_training_readiness_range,
                start_text,
                end_text,
            ),
            "weekly_status": call_section(
                errors,
                "weekly_training_status",
                client.get_weekly_training_status,
                start_text,
                end_text,
            ),
            "current_status": call_section(
                errors, "training_status", client.get_training_status, end_text
            ),
            "load_balance": call_section(
                errors,
                "training_load_balance",
                client.get_training_four_week_load_balance,
                end_text,
            ),
        },
        "health": {
            "daily_summaries": call_section(
                errors, "daily_summaries", client.get_daily_summaries, start_text, end_text
            ),
            "heart_rate": call_section(
                errors,
                "heart_rate",
                client.get_daily_heart_rate_stats,
                start_text,
                end_text,
            ),
            "hrv": call_section(
                errors, "hrv", client.get_hrv_data_range, start_text, end_text
            ),
            "stress": call_section(
                errors, "stress", client.get_daily_stress_stats, start_text, end_text
            ),
            "body_battery": call_section(
                errors,
                "body_battery",
                client.get_daily_body_battery_stats,
                start_text,
                end_text,
            ),
            "intensity_minutes": call_section(
                errors,
                "intensity_minutes",
                client.get_daily_intensity_minutes_stats,
                start_text,
                end_text,
            ),
            "respiration": call_section(
                errors,
                "respiration",
                client.get_daily_respiration_stats,
                start_text,
                end_text,
            ),
            "body_composition": call_section(
                errors,
                "body_composition",
                client.get_body_composition,
                start_text,
                end_text,
            ),
            "sleep": sleep,
        },
        "errors": errors,
    }


def item_count(value: Any) -> int | None:
    if isinstance(value, (list, dict)):
        return len(value)
    return None


def write_brief(bundle: dict[str, Any], path: Path) -> None:
    meta = bundle["metadata"]
    lines = [
        "# Garmin analysis evidence",
        "",
        f"- Range: {meta['start_date']} to {meta['end_date']}",
        f"- Sleep detail starts: {meta['sleep_start_date']}",
        f"- Source: {meta['source']}",
        f"- Endpoint errors: {len(bundle['errors'])}",
        "",
        "## Available sections",
        "",
    ]
    for group_name in ("training", "health"):
        for name, value in bundle[group_name].items():
            count = item_count(value)
            state = "missing" if value is None else "available"
            suffix = f", {count} top-level items" if count is not None else ""
            lines.append(f"- `{group_name}.{name}`: {state}{suffix}")
    if bundle["errors"]:
        lines.extend(["", "## Fetch warnings", ""])
        for error in bundle["errors"]:
            lines.append(f"- `{error['section']}`: {error['error']}")
    lines.extend(
        [
            "",
            "## Analysis instruction",
            "",
            "Compare recent training load and activity volume with sleep, HRV, resting heart "
            "rate, stress, Body Battery, and readiness. State missing coverage and separate "
            "observations from inference. Do not provide a medical diagnosis.",
            "",
            meta["attribution"],
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=28, help="range length, 1-90")
    parser.add_argument("--end-date", type=parse_iso_date, help="YYYY-MM-DD")
    parser.add_argument(
        "--sleep-days", type=int, default=14, help="daily sleep detail days, 1-31"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--interactive-auth",
        action="store_true",
        help="prompt locally for missing username, password, and phone verification code",
    )
    parser.add_argument(
        "--auth-only",
        action="store_true",
        help="obtain/reuse a token without fetching training or health data",
    )
    parser.add_argument(
        "--include-location",
        action="store_true",
        help="retain exact route/location fields in output",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.sleep_days <= 31:
        print("error: --sleep-days must be between 1 and 31", file=sys.stderr)
        return 2
    try:
        start, end = date_window(args.days, args.end_date)
        client = build_client(interactive_auth=args.interactive_auth)
        if args.auth_only:
            print("Garmin authentication successful.")
            return 0
        bundle = collect(client, start, end, min(args.sleep_days, args.days))
        bundle = redact(bundle, include_location=args.include_location)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        brief_path = args.output.with_name("analysis-brief.md")
        write_brief(bundle, brief_path)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(args.output)
    print(brief_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
