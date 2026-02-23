from pathlib import Path
import sys

# Permet l'exécution via `pytest` sans dépendre d'un PYTHONPATH externe.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import qa_autopilot


class DummyPage:
    def __init__(self):
        self.url = "https://example.test"


def test_get_console_errors_filters_only_errors():
    interceptor = qa_autopilot.QAInterceptor(DummyPage())
    interceptor._console = [
        qa_autopilot.CapturedConsole(type="warning", text="warn", url=""),
        qa_autopilot.CapturedConsole(type="error", text="err", url=""),
        qa_autopilot.CapturedConsole(type="info", text="info", url=""),
    ]

    errors = interceptor.get_console_errors()

    assert [entry["type"] for entry in errors] == ["error"]


def test_build_failure_context_keeps_warnings_separate_from_errors():
    interceptor = qa_autopilot.QAInterceptor(DummyPage())
    interceptor._console = [
        qa_autopilot.CapturedConsole(type="warning", text="warn", url=""),
        qa_autopilot.CapturedConsole(type="error", text="err", url=""),
    ]

    ctx = interceptor.build_failure_context("boom")

    assert [entry["type"] for entry in ctx.console_errors] == ["error"]
    assert [entry["type"] for entry in ctx.console_warnings] == ["warning"]


def test_build_pytest_command_does_not_use_invalid_dash_c_for_conftest():
    cmd = qa_autopilot.build_pytest_command(["tests/"], "python")

    assert "-c" not in cmd
    assert cmd[:5] == ["python", "-m", "pytest", "--qa-autopilot", "-v"]
    assert cmd[-1] == "tests/"
