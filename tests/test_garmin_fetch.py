import importlib.util
import io
import os
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch


SCRIPT = (
    Path(__file__).parents[1]
    / ".agents/skills/garmin-cn-analysis/scripts/garmin_fetch.py"
)
SPEC = importlib.util.spec_from_file_location("garmin_fetch", SCRIPT)
garmin_fetch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(garmin_fetch)


class DateWindowTests(unittest.TestCase):
    def test_inclusive_window(self):
        self.assertEqual(
            garmin_fetch.date_window(7, date(2026, 11, 13)),
            (date(2026, 11, 7), date(2026, 11, 13)),
        )

    def test_rejects_oversized_window(self):
        with self.assertRaises(ValueError):
            garmin_fetch.date_window(91, date(2026, 11, 13))


class RedactionTests(unittest.TestCase):
    def test_removes_secrets_identity_and_location_recursively(self):
        raw = {
            "accessToken": "secret",
            "displayName": "athlete",
            "activity": {
                "startLatitude": 31.2,
                "longitude": 121.4,
                "distance": 5000,
            },
        }
        self.assertEqual(
            garmin_fetch.redact(raw),
            {"activity": {"distance": 5000}},
        )

    def test_location_can_be_explicitly_retained(self):
        self.assertEqual(
            garmin_fetch.redact({"startLatitude": 31.2}, include_location=True),
            {"startLatitude": 31.2},
        )

    def test_exception_text_redacts_email_and_bearer_token(self):
        error = RuntimeError("user@example.com Bearer abc.def.ghi")
        result = garmin_fetch.safe_exception(error)
        self.assertNotIn("user@example.com", result)
        self.assertNotIn("abc.def.ghi", result)


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        class AuthenticationError(Exception):
            pass

        self.auth_error = AuthenticationError
        self.restore = Mock()
        self.fresh = Mock()
        self.factory = Mock(side_effect=[self.restore, self.fresh])
        module = types.ModuleType("garminconnect")
        module.Garmin = self.factory
        module.GarminConnectAuthenticationError = AuthenticationError
        self.env_patch = patch.dict(os.environ, {}, clear=True)
        self.module_patch = patch.dict("sys.modules", {"garminconnect": module})
        self.env_patch.start()
        self.module_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.addCleanup(self.module_patch.stop)

    def require_credentials(self):
        self.restore.login.side_effect = self.auth_error("No valid tokens")

    def submit_code(self, source):
        # Simulate Garmin requesting verification only after credentials are submitted.
        self.assertEqual(self.factory.call_args.kwargs["email"], "athlete")
        self.assertEqual(self.factory.call_args.kwargs["password"], "test-password")
        self.assertEqual(
            self.factory.call_args.kwargs["prompt_mfa"](), "123456"
        )

    def test_interactive_username_password_then_phone_code_are_saved(self):
        self.require_credentials()
        self.fresh.login.side_effect = self.submit_code
        with patch("builtins.input", return_value=" athlete ") as username_input, patch.object(
            garmin_fetch.getpass, "getpass", side_effect=["test-password", " 123456 "]
        ) as secret_input:
            client = garmin_fetch.build_client(interactive_auth=True)
        self.assertIs(client, self.fresh)
        self.assertEqual(username_input.call_count, 1)
        self.assertEqual(secret_input.call_count, 2)
        self.assertTrue(self.factory.call_args.kwargs["is_cn"])
        self.fresh.login.assert_called_once_with(".garmin-tokens")
        self.fresh.client.dump.assert_called_once_with(".garmin-tokens")

    def test_valid_local_token_skips_all_prompts_and_retains_refresh(self):
        with patch("builtins.input") as username_input, patch.object(
            garmin_fetch.getpass, "getpass"
        ) as secret_input:
            self.assertIs(garmin_fetch.build_client(True), self.restore)
        username_input.assert_not_called()
        secret_input.assert_not_called()
        self.factory.assert_called_once()
        self.restore.login.assert_called_once_with(".garmin-tokens")
        self.restore.client.dump.assert_called_once_with(".garmin-tokens")

    def test_inline_cloud_token_has_priority_and_is_not_written_to_disk(self):
        token_json = '{"di_token": "test-token"}'
        os.environ.update(GARMIN_TOKENS_JSON=token_json, GARMIN_TOKEN_STORE="local-cache")
        with patch("builtins.input") as username_input, patch.object(
            garmin_fetch.getpass, "getpass"
        ) as secret_input:
            self.assertIs(garmin_fetch.build_client(True), self.restore)
        self.restore.login.assert_called_once_with(token_json)
        self.restore.client.dump.assert_not_called()
        username_input.assert_not_called()
        secret_input.assert_not_called()

    def test_environment_username_and_legacy_email_support(self):
        for identity in ({"GARMIN_USERNAME": "athlete", "GARMIN_EMAIL": "legacy"},
                         {"GARMIN_EMAIL": "athlete"}):
            with self.subTest(identity=identity), patch.dict(os.environ, {
                **identity, "GARMIN_PASSWORD": "test-password",
                "GARMIN_MFA_CODE": " 123456 ", "GARMIN_TOKEN_STORE": "custom-cache",
            }, clear=True):
                self.factory.reset_mock(side_effect=True)
                self.factory.side_effect = [self.restore, self.fresh]
                self.require_credentials()
                self.fresh.reset_mock()
                self.fresh.login.side_effect = self.submit_code
                with patch("builtins.input") as username_input, patch.object(
                    garmin_fetch.getpass, "getpass"
                ) as secret_input:
                    garmin_fetch.build_client()
                username_input.assert_not_called()
                secret_input.assert_not_called()
                self.fresh.client.dump.assert_called_once_with("custom-cache")

    def test_missing_credentials_do_not_prompt_in_noninteractive_mode(self):
        self.require_credentials()
        with patch("builtins.input") as username_input, patch.object(
            garmin_fetch.getpass, "getpass"
        ) as secret_input, self.assertRaisesRegex(RuntimeError, "GARMIN_USERNAME"):
            garmin_fetch.build_client()
        username_input.assert_not_called()
        secret_input.assert_not_called()
        self.fresh.login.assert_not_called()

    def test_missing_or_empty_verification_code_is_not_saved(self):
        for interactive in (False, True):
            with self.subTest(interactive=interactive), patch.dict(os.environ, {
                "GARMIN_USERNAME": "athlete", "GARMIN_PASSWORD": "test-password",
            }, clear=True):
                self.factory.reset_mock(side_effect=True)
                self.factory.side_effect = [self.restore, self.fresh]
                self.require_credentials()
                self.fresh.login.side_effect = lambda source: self.factory.call_args.kwargs["prompt_mfa"]()
                with patch.object(garmin_fetch.getpass, "getpass", return_value=" "), self.assertRaisesRegex(
                    RuntimeError, "phone verification code"
                ):
                    garmin_fetch.build_client(interactive)
                self.fresh.client.dump.assert_not_called()

    def test_one_time_environment_code_is_not_reused(self):
        self.require_credentials()
        os.environ.update(GARMIN_USERNAME="athlete", GARMIN_PASSWORD="test-password",
                          GARMIN_MFA_CODE="123456")

        def repeated_challenge(source):
            prompt = self.factory.call_args.kwargs["prompt_mfa"]
            self.assertEqual(prompt(), "123456")
            prompt()

        self.fresh.login.side_effect = repeated_challenge
        with self.assertRaisesRegex(RuntimeError, "GARMIN_MFA_CODE"):
            garmin_fetch.build_client()
        self.fresh.client.dump.assert_not_called()

    def test_network_or_rate_limit_stops_without_credential_login(self):
        self.restore.login.side_effect = RuntimeError("sensitive response")
        with patch("builtins.input") as username_input, self.assertRaises(RuntimeError) as error:
            garmin_fetch.build_client(True)
        self.assertNotIn("sensitive response", str(error.exception))
        username_input.assert_not_called()
        self.fresh.login.assert_not_called()

    def test_bad_credentials_or_code_do_not_expose_secret_response(self):
        self.require_credentials()
        os.environ.update(GARMIN_USERNAME="athlete", GARMIN_PASSWORD="test-password")
        self.fresh.login.side_effect = self.auth_error("test-password token=secret 123456")
        with self.assertRaises(RuntimeError) as error:
            garmin_fetch.build_client()
        for secret in ("test-password", "token=secret", "123456"):
            self.assertNotIn(secret, str(error.exception))
        self.fresh.client.dump.assert_not_called()

    def test_token_persistence_failure_is_reported(self):
        self.restore.client.dump.side_effect = PermissionError("secret response")
        with self.assertRaisesRegex(RuntimeError, "token saving failed") as error:
            garmin_fetch.build_client()
        self.assertNotIn("secret response", str(error.exception))


class AuthenticationCommandTests(unittest.TestCase):
    def test_auth_only_skips_data_collection_and_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "garmin-data.json"
            with patch.object(garmin_fetch, "build_client") as build_client, patch.object(
                garmin_fetch, "collect"
            ) as collect, redirect_stdout(io.StringIO()) as stdout:
                result = garmin_fetch.main([
                    "--interactive-auth", "--auth-only", "--output", str(output)
                ])
            self.assertEqual(result, 0)
            build_client.assert_called_once_with(interactive_auth=True)
            collect.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertIn("successful", stdout.getvalue())

    def test_auth_failure_returns_nonzero(self):
        with patch.object(garmin_fetch, "build_client", side_effect=RuntimeError("Login failed")), patch.object(
            garmin_fetch, "collect"
        ) as collect, redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(garmin_fetch.main(["--auth-only"]), 1)
        collect.assert_not_called()
        self.assertIn("Login failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
