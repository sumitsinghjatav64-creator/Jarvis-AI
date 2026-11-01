import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_action_module():
    import importlib.util

    path = PROJECT_ROOT / "actions" / "youtu_agent.py"
    spec = importlib.util.spec_from_file_location("actions.youtu_agent_test", path)
    if spec is None or spec.loader is None:
        raise AssertionError("Youtu-Agent action module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class YoutuAgentActionTests(unittest.TestCase):
    def test_action_module_is_discoverable(self):
        path = PROJECT_ROOT / "actions" / "youtu_agent.py"
        self.assertTrue(path.is_file(), "expected a drop-in JARVIS action module")

    def test_empty_task_is_rejected_before_loading_youtu(self):
        module = _load_action_module()
        with patch.object(module, "_load_youtu_api", side_effect=AssertionError("must stay lazy")):
            result = module.run_youtu_agent({"task": "  "})
        self.assertIn("task", result.lower())

    def test_missing_model_settings_are_reported_without_importing_youtu(self):
        module = _load_action_module()
        with patch.dict(os.environ, {}, clear=False):
            for key in ("UTU_LLM_API_KEY", "UTU_LLM_BASE_URL", "UTU_LLM_MODEL"):
                os.environ.pop(key, None)
            with patch.object(module, "_load_youtu_api", side_effect=AssertionError("must stay lazy")):
                result = module.run_youtu_agent({"task": "summarize a local design"})
        self.assertIn("UTU_LLM_API_KEY", result)
        self.assertIn("UTU_LLM_BASE_URL", result)
        self.assertIn("UTU_LLM_MODEL", result)

    def test_text_only_run_uses_base_env_and_does_not_log_trajectory(self):
        module = _load_action_module()
        captured = {}

        class FakeConfig:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class FakeAgent:
            def __init__(self, *, config):
                captured["config"] = config

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def run(self, task, **kwargs):
                captured["task"] = task
                captured["run_kwargs"] = kwargs
                res = SimpleNamespace()
                res.final_output = "Youtu result"
                return res

        fake_api = {
            "SimpleAgent": FakeAgent,
            "AgentConfig": FakeConfig,
            "ProfileConfig": FakeConfig,
            "EnvConfig": FakeConfig,
            "ContextManagerConfig": FakeConfig,
            "ModelConfigs": FakeConfig,
            "ModelProviderConfig": FakeConfig,
        }
        with patch.dict(os.environ, {
            "UTU_LLM_API_KEY": "test-key-never-print",
            "UTU_LLM_BASE_URL": "https://model.example/v1",
            "UTU_LLM_MODEL": "test-model",
            "UTU_LLM_TYPE": "chat.completions",
        }, clear=False), patch.object(module, "_load_youtu_api", return_value=fake_api):
            result = module.run_youtu_agent({"task": "analyze this text"})

        self.assertEqual(result, "Youtu result")
        self.assertEqual(captured["config"].env.name, "base")
        self.assertEqual(captured["config"].toolkits, {})
        self.assertFalse(captured["run_kwargs"]["log_to_db"])
        self.assertFalse(captured["run_kwargs"]["save"])
        self.assertNotIn("test-key-never-print", result)

    def test_runtime_error_does_not_echo_credentials(self):
        module = _load_action_module()
        secret = "test-key-do-not-return"

        class FakeAgent:
            def __init__(self, *, config):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def run(self, _task, **_kwargs):
                raise RuntimeError(f"provider rejected credential {secret}")

        fake_api = {
            "SimpleAgent": FakeAgent,
            "AgentConfig": lambda **kwargs: SimpleNamespace(**kwargs),
            "ProfileConfig": lambda **kwargs: SimpleNamespace(**kwargs),
            "EnvConfig": lambda **kwargs: SimpleNamespace(**kwargs),
            "ContextManagerConfig": lambda **kwargs: SimpleNamespace(**kwargs),
            "ModelConfigs": lambda **kwargs: SimpleNamespace(**kwargs),
            "ModelProviderConfig": lambda **kwargs: SimpleNamespace(**kwargs),
        }
        with patch.dict(os.environ, {
            "UTU_LLM_API_KEY": secret,
            "UTU_LLM_BASE_URL": "https://model.example/v1",
            "UTU_LLM_MODEL": "test-model",
        }, clear=False), patch.object(module, "_load_youtu_api", return_value=fake_api):
            result = module.run_youtu_agent({"task": "a small task"})
        self.assertNotIn(secret, result)
        self.assertIn("failed", result.lower())


class YoutuAgentRuntimeIsolationTests(unittest.TestCase):
    def test_invokes_isolated_runtime_with_task_on_stdin(self):
        import subprocess

        module = _load_action_module()
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"ok": true, "output": "Youtu result"}', stderr=""
        )
        with patch.dict(os.environ, {
            "UTU_LLM_API_KEY": "test-key-never-print",
            "UTU_LLM_BASE_URL": "https://model.example/v1",
            "UTU_LLM_MODEL": "test-model",
        }, clear=False), patch.object(module, "_runtime_python", return_value=Path("C:/runtime/python.exe"), create=True), patch(
            "subprocess.run", return_value=completed
        ) as run:
            result = module.run_youtu_agent({"task": "run a text analysis"})
            if "Youtu-Agent is not installed" in result:
                self.skipTest("Youtu-Agent optional package is not installed in this environment.")

        self.assertEqual(result, "Youtu result")
        run.assert_called_once()
        kwargs = run.call_args.kwargs
        self.assertNotIn("shell", kwargs)
        self.assertIn("run a text analysis", kwargs["input"])
        self.assertNotIn("test-key-never-print", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
