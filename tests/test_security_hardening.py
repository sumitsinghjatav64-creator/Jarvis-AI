import unittest
from unittest.mock import patch

from core.safe_command import parse_safe_command
from core.web_security import same_origin_request
from actions import github_repo_manager


class SafeCommandTests(unittest.TestCase):
    def test_allows_only_exact_read_only_commands(self):
        self.assertEqual(parse_safe_command("whoami", system="Linux"), ["/usr/bin/whoami"])
        self.assertEqual(parse_safe_command("ps aux", system="Linux"), ["/bin/ps", "aux"])

    def test_rejects_shells_chains_and_unapproved_commands(self):
        for command in (
            "python -c print(1)",
            "whoami && del important.txt",
            "powershell Remove-Item *",
            "echo hello > file.txt",
            "",
        ):
            with self.subTest(command=command):
                self.assertIsNone(parse_safe_command(command, system="Windows"))

    def test_windows_commands_resolve_to_system_directory(self):
        argv = parse_safe_command("tasklist", system="Windows", system_root="C:/Windows")
        self.assertEqual(argv, ["C:/Windows/System32/tasklist.exe"])


class ConfirmedRepositoryCommandTests(unittest.TestCase):
    @patch.object(github_repo_manager, "run_repo_command", return_value="ran safely")
    @patch("core.confirm.request", return_value="[CONFIRMATION_PENDING]")
    def test_repository_command_is_not_run_before_confirmation(self, request, run):
        result = github_repo_manager.github_manager({
            "action": "run",
            "repo_name": "demo",
            "command": "python build.py",
        })
        self.assertEqual(result, "[CONFIRMATION_PENDING]")
        run.assert_not_called()
        self.assertIn("python build.py", request.call_args.kwargs["detail"])
        self.assertEqual(request.call_args.kwargs["run"](), "ran safely")
        run.assert_called_once_with("demo", "python build.py")


class WebSocketOriginTests(unittest.TestCase):
    def test_accepts_only_matching_http_origin_and_host(self):
        self.assertTrue(same_origin_request("http://127.0.0.1:8765", "127.0.0.1:8765"))
        self.assertFalse(same_origin_request("https://evil.example", "127.0.0.1:8765"))
        self.assertFalse(same_origin_request("", "127.0.0.1:8765"))
        self.assertFalse(same_origin_request("http://127.0.0.1:9999", "127.0.0.1:8765"))
        self.assertFalse(same_origin_request("http://user@127.0.0.1:8765", "127.0.0.1:8765"))


if __name__ == "__main__":
    unittest.main()
