import sys
import os
import json
import subprocess
import pytest
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt

# --- Gör så att pytest hittar src/main.py i överordnad katalog ---
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.main import (
    sanitize_json_like,
    load_all_configs,
    CommandRunner,
    ValidatorThread,
    WorkerSignals,
    TaskWidget,
)

# -----------------------------
#  GLOBAL FIXTURES
# -----------------------------


@pytest.fixture(scope="session")
def app():
    """Skapa en QApplication för PyQt-tester."""
    return QApplication([])


# -----------------------------
#  TEST: sanitize_json_like
# -----------------------------


def test_sanitize_json_like_basic():
    text = "{'key': 'value'}"
    fixed = sanitize_json_like(text)
    assert '"' in fixed
    assert '"key":' in fixed
    assert fixed.startswith("{")
    assert fixed.endswith("}")


def test_sanitize_json_like_unquoted_keys():
    text = "{key1: 'a', key2: 'b',}"
    result = sanitize_json_like(text)
    assert '"a"' in result
    assert '"b"' in result
    # kontrollera att det inte finns ogiltig JSON-syntax (t.ex. dubbla komman)
    assert not result.endswith(",")


# -----------------------------
#  TEST: load_all_configs
# -----------------------------


def test_load_all_configs_merges_json(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")

    cfg1 = {"os": "linux", "projectname": "Alpha", "tasks": [{"name": "T1"}]}
    cfg2 = {"os": "linux", "projectname": "Beta", "tasks": [{"name": "T2"}]}
    (tmp_path / "a.json").write_text(json.dumps(cfg1), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(cfg2), encoding="utf-8")

    merged = load_all_configs(tmp_path)
    assert len(merged["tasks"]) == 2


def test_load_all_configs_skips_wrong_os(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    cfg = {"os": "windows", "projectname": "WinOnly", "tasks": [{"name": "WinTask"}]}
    (tmp_path / "win.json").write_text(json.dumps(cfg), encoding="utf-8")

    merged = load_all_configs(tmp_path)
    assert merged["tasks"] == []


# -----------------------------
#  TEST: Worker classes
# -----------------------------


class DummySignals(WorkerSignals):
    def __init__(self):
        super().__init__()
        self.logs = []
        self.progress_values = []
        self.updates = []
        self.finished_called = False
        self.log.connect(self.logs.append)
        self.progress.connect(self.progress_values.append)
        self.task_update.connect(lambda i, v: self.updates.append((i, v)))
        self.finished.connect(self._finished)

    def _finished(self):
        self.finished_called = True


def test_commandrunner_writes_log(tmp_path):
    log = tmp_path / "log.txt"
    sig = DummySignals()
    runner = CommandRunner(["echo test123"], log, sig)
    runner.run()
    text = log.read_text(encoding="utf-8")
    assert "test123" in text
    assert sig.finished_called
    assert any(v == 100 for v in sig.progress_values)


def test_validatorthread_emits_updates(monkeypatch):
    class DummyResult:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: DummyResult())

    sig = DummySignals()
    tasks = [{"validate": ["echo hi"]}, {"validate": ["false"]}]
    v = ValidatorThread(tasks, Path("fake.log"), sig)
    v.run()
    assert sig.updates[0] == (0, True)
    assert len(sig.updates) == 2


# -----------------------------
#  TEST: TaskWidget
# -----------------------------


def test_taskwidget_toggle_checkbox(app):
    w = TaskWidget(0, {"name": "Demo"})
    assert not w.checkbox.isChecked()
    # använd riktig mus-simulering för att undvika Windows crash
    QTest.mouseClick(w, Qt.LeftButton)
    assert w.checkbox.isChecked()


def test_taskwidget_set_valid(app):
    w = TaskWidget(0, {"name": "Demo"})
    w.set_valid(True)
    style = w.status_label.styleSheet()
    assert "#00ff55" in style
    w.set_valid(False)
    assert "#ff5555" in w.status_label.styleSheet()
