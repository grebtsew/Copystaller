#!/usr/bin/env python3
"""
copystaller.py — Modern Dark Mode Edition 🌙
A stylish PyQt5-based GUI for running install/uninstall tasks from JSON config.
"""

import platform
from pathlib import Path
import json
import time
import sys
import os
import re
import subprocess
import datetime
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QCheckBox,
    QScrollArea,
    QMessageBox,
    QGraphicsDropShadowEffect,
)
from PyQt5.QtGui import QColor, QPalette

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# ---------------------------- JSON FIX HELP -----------------------------------


def sanitize_json_like(text: str) -> str:
    text = text.replace("\\'", "\\\\'")
    text = text.replace("'", '"')
    text = re.sub(
        r"(?P<prefix>[{,\\s\\[])(?P<key>[A-Za-z0-9_\\-]+)\\s*:",
        r'\\g<prefix>"\\g<key>":',
        text,
    )
    text = re.sub(r",\\s*([}\\]])", r"\\1", text)
    return text


# ---------------------------- WORKER CLASSES ----------------------------------


class WorkerSignals(QObject):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    task_update = pyqtSignal(int, bool)
    finished = pyqtSignal()


class CommandRunner(QThread):
    def __init__(self, commands, logger_path: Path, signals: WorkerSignals, cwd=None):
        super().__init__()
        self.commands = commands
        self.logger_path = logger_path
        self.signals = signals
        self.cwd = cwd or os.getcwd()

    def run(self):
        is_windows = platform.system().lower() == "windows"
        total = len(self.commands)
        for i, cmd in enumerate(self.commands, start=1):
            timestamp = datetime.datetime.now().isoformat()
            header = f"\n[{timestamp}] ⚡ >>> {cmd}\n"
            self._append_log(header)
            self.signals.log.emit(header)
            try:
                if is_windows:
                    proc = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        cwd=self.cwd,
                    )
                else:
                    proc = subprocess.Popen(
                        cmd,
                        shell=True,
                        executable="/bin/bash",
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        cwd=self.cwd,
                    )

                for line in proc.stdout:
                    decoded = line.decode("utf-8", errors="replace")
                    self._append_log(decoded)
                    self.signals.log.emit(decoded)

                proc.wait()
                exitcode = proc.returncode
                footer = f"{'✅' if exitcode==0 else '❌'} [exit {exitcode}]\n"
                self._append_log(footer)
                self.signals.log.emit(footer)
            except Exception as e:
                err = f"❌ Exception running command: {e}\n"
                self._append_log(err)
                self.signals.log.emit(err)

            percent = int((i / total) * 100)
            self.signals.progress.emit(percent)

        self.signals.finished.emit()

    def _append_log(self, text: str):
        text = text.replace("\\n", "\n")
        with open(self.logger_path, "a", encoding="utf-8") as f:
            f.write(text)


class ValidatorThread(QThread):
    def __init__(self, tasks, logger_path: Path, signals: WorkerSignals):
        super().__init__()
        self.tasks = tasks
        self.logger_path = logger_path
        self.signals = signals
        self.is_windows = platform.system().lower() == "windows"

    def run(self):
        for idx, task in enumerate(self.tasks):
            valid = False
            val_cmds = task.get("validate", []) or []
            for cmd in val_cmds:
                try:
                    if self.is_windows:
                        completed = subprocess.run(
                            cmd,
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=None,
                        )
                    else:
                        completed = subprocess.run(
                            cmd,
                            shell=True,
                            executable="/bin/bash",
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=None,
                        )
                    if completed.returncode == 0:
                        valid = True
                        break
                except Exception:
                    valid = False
            self.signals.task_update.emit(idx, valid)


# ---------------------------- GUI COMPONENTS ----------------------------------


class TaskWidget(QWidget):
    def __init__(self, index: int, task: dict):
        super().__init__()
        self.index = index
        self.task = task
        self.setMouseTracking(True)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(5, 5, 5, 5)
        self.card = QWidget()
        self.card.setObjectName("TaskCard")
        self.card.setMouseTracking(True)
        layout = QHBoxLayout(self.card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(15)

        self.checkbox = QCheckBox()
        layout.addWidget(self.checkbox)
        self.name_label = QLabel(task.get("name", f"Task {index}"))
        self.name_label.setObjectName("TaskName")
        layout.addWidget(self.name_label, stretch=1)
        self.status_label = QLabel()
        self.status_label.setFixedSize(18, 18)
        self.status_label.setStyleSheet("border-radius:9px; background-color: gray;")
        layout.addWidget(self.status_label)
        self.card.setLayout(layout)
        outer_layout.addWidget(self.card)

        self.default_bg = "#1E1E1E"
        self.hover_bg = "#2A2A2A"
        self.selected_bg = "#3A3F58"
        self.default_border = "#2F2F2F"
        self.hover_border = "#4D6CFA"
        self.selected_border = "#7AA2F7"

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(30)
        self.shadow.setOffset(0, 6)
        self.shadow.setColor(QColor(0, 0, 0, 180))
        self.card.setGraphicsEffect(self.shadow)

        self.is_hovered = False
        self.update_style()

    def update_style(self):
        if self.checkbox.isChecked():
            bg = self.selected_bg
            border = self.selected_border
        elif self.is_hovered:
            bg = self.hover_bg
            border = self.hover_border
        else:
            bg = self.default_bg
            border = self.default_border
        self.card.setStyleSheet(
            f"""
            QWidget#TaskCard {{
                background-color: {bg};
                border-radius: 14px;
                border: 2px solid {border};
            }}
            #TaskName {{
                color: #f0f0f0;
                font-size: 13pt;
                font-weight: 500;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #cccccc;
                background-color: #1e1e1e;
            }}
            QCheckBox::indicator:checked {{
                background-color: #00c6ff;
                border: 2px solid #00caff;
            }}
        """
        )

    def set_valid(self, is_valid: bool):
        color = "#00ff55" if is_valid else "#ff5555"
        self.status_label.setStyleSheet(
            f"border-radius:9px; background-color:{color}; border: 1px solid #202020;"
        )

    def is_checked(self):
        return self.checkbox.isChecked()

    def mousePressEvent(self, event):
        self.checkbox.setChecked(not self.checkbox.isChecked())
        self.update_style()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.is_hovered = True
        self.update_style()
        self.shadow.setEnabled(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update_style()
        self.shadow.setEnabled(False)
        super().leaveEvent(event)


# ---------------------------- MAIN WINDOW -------------------------------------


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.runner_start_time = None
        self.setWindowTitle("Copystaller ⚙️")
        self.config = config
        if not self.config:
            QMessageBox.critical(self, "❌ Error", "Invalid or empty config!")
            sys.exit(1)

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = LOG_DIR / f"copystaller_{ts}.log"
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(
                f"== Copystaller log started {datetime.datetime.now().isoformat()} ==\n"
            )

        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        self.setCentralWidget(central)

        title = QLabel(self.config.get("projectname", "Copystaller Project"))
        title.setStyleSheet(
            "font-size: 22pt; font-weight: 600; color: #ffffff; margin-bottom: 10px;"
        )
        main_layout.addWidget(title)

        self.tasks = self.config.get("tasks", [])
        self.task_widgets = []

        tasks_container = QWidget()
        self.scroll_widget_layout = QVBoxLayout(tasks_container)
        self.scroll_widget_layout.setSpacing(10)
        self.scroll_widget_layout.setContentsMargins(0, 0, 0, 0)

        for i, t in enumerate(self.tasks):
            tw = TaskWidget(i, t)
            self.scroll_widget_layout.addWidget(tw)
            self.task_widgets.append(tw)
        self.scroll_widget_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tasks_container)
        scroll.setStyleSheet("background-color: transparent; border: none;")
        main_layout.addWidget(scroll, stretch=2)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        self.install_btn = QPushButton("⚡ Install")
        self.uninstall_btn = QPushButton("🗑 Uninstall")
        self.refresh_btn = QPushButton("🔄 Refresh")
        btn_layout.addWidget(self.install_btn)
        btn_layout.addWidget(self.uninstall_btn)
        btn_layout.addWidget(self.refresh_btn)
        main_layout.addLayout(btn_layout)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(10)
        self.progress.setStyleSheet(
            """
            QProgressBar { background-color: #1e1e1e; border-radius: 5px; }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #00c6ff, stop:1 #0072ff); border-radius: 5px;
            }
        """
        )
        main_layout.addWidget(self.progress)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet(
            """
            QTextEdit { background-color: #151515; color: #dcdcdc; border-radius: 8px;
            font-family: Consolas, monospace; font-size: 10pt; padding: 8px; }
            QScrollBar:vertical { background: #2b2b2b; width: 12px; border-radius: 6px; }
            QScrollBar::handle:vertical { background: #505050; min-height: 20px; border-radius: 6px; }
            QScrollBar::handle:vertical:hover { background: #888888; }
            QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }
        """
        )
        main_layout.addWidget(self.log_output, stretch=1)

        btn_style = """
            QPushButton {
                background-color: #303030;
                border: 1px solid #505050;
                color: white;
                font-weight: 500;
                padding: 10px 20px;
                border-radius: 10px;
                font-size: 11pt;
            }
            QPushButton:hover { background-color: #3d3d3d; border: 1px solid #00aaff; }
            QPushButton:pressed { background-color: #007acc; }
        """
        self.install_btn.setStyleSheet(btn_style)
        self.uninstall_btn.setStyleSheet(btn_style.replace("#00aaff", "#ff5555"))
        self.refresh_btn.setStyleSheet(btn_style)

        self.signals = WorkerSignals()
        self.signals.progress.connect(self.progress.setValue)
        self.signals.log.connect(self.append_log)
        self.signals.task_update.connect(self.on_task_update)
        self.signals.finished.connect(self.on_finished)

        self.install_btn.clicked.connect(self.install_selected)
        self.uninstall_btn.clicked.connect(self.uninstall_selected)
        self.refresh_btn.clicked.connect(self.refresh_config)

        self.validator = ValidatorThread(self.tasks, self.log_path, self.signals)
        self.validator.start()

        self.apply_dark_theme()
        self.adjustSize()

    # ---------- Logging ----------
    def append_log(self, text, color="#dcdcdc"):
        text = text.replace("\\n", "\n")
        cursor = self.log_output.textCursor()
        cursor.movePosition(cursor.End)
        self.log_output.setTextCursor(cursor)
        self.log_output.insertPlainText(text)
        self.log_output.moveCursor(cursor.End)

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"{text}")

    # ---------- Dark theme ----------
    def apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(25, 25, 25))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(18, 18, 18))
        palette.setColor(QPalette.AlternateBase, QColor(40, 40, 40))
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(40, 40, 40))
        palette.setColor(QPalette.ButtonText, Qt.white)

        self.setPalette(palette)

    # ---------- Task logic ----------
    def install_selected(self):

        commands = [
            cmd
            for tw in self.task_widgets
            if tw.is_checked()
            for cmd in self.config["tasks"][tw.index].get("install", [])
        ]
        if not commands:
            QMessageBox.information(
                self, "⚡ No task", "Select at least one task with install commands."
            )
            return
        self.disable_ui()
        self.runner_start_time = time.time()
        self.runner = CommandRunner(commands, self.log_path, self.signals)
        self.runner.start()

    def uninstall_selected(self):

        commands = [
            cmd
            for tw in self.task_widgets
            if tw.is_checked()
            for cmd in self.config["tasks"][tw.index].get("uninstall", [])
        ]
        if not commands:
            QMessageBox.information(
                self, "🗑 No task", "Select at least one task with uninstall commands."
            )
            return
        self.disable_ui()
        self.runner_start_time = time.time()
        self.runner = CommandRunner(commands, self.log_path, self.signals)
        self.runner.start()

    def on_task_update(self, idx, valid):
        if 0 <= idx < len(self.task_widgets):
            self.task_widgets[idx].set_valid(valid)

    def on_finished(self):
        self.progress.setValue(100)
        self.enable_ui()

        elapsed = 0
        if self.runner_start_time:
            elapsed = time.time() - self.runner_start_time
            self.append_log(f"\n⏱ Duration: {elapsed:.2f} seconds\n")

        QMessageBox.information(
            self, "Done ✅", f"All tasks finished. Duration: {elapsed:.2f} seconds"
        )

        time.sleep(1)
        self.run_validator()

    def disable_ui(self):
        self.install_btn.setEnabled(False)
        self.uninstall_btn.setEnabled(False)
        for tw in self.task_widgets:
            tw.checkbox.setEnabled(False)

    def enable_ui(self):
        self.install_btn.setEnabled(True)
        self.uninstall_btn.setEnabled(True)
        for tw in self.task_widgets:
            tw.checkbox.setEnabled(True)

    def refresh_config(self):
        self.append_log("\n🔄 [INFO] Refreshing configuration...\n")
        try:
            new_cfg = load_all_configs(Path("."))
            if not new_cfg or not new_cfg.get("tasks"):
                self.append_log("❌ [ERROR] No valid tasks found in JSON files.\n")
                QMessageBox.warning(
                    self, "No config", "No valid tasks found in JSON files."
                )
                return
        except Exception as e:
            self.append_log(f"❌ [ERROR] Failed to load JSON configs: {e}\n")
            return

        self.config = new_cfg
        self.tasks = new_cfg.get("tasks", [])

        while self.scroll_widget_layout.count():
            item = self.scroll_widget_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.task_widgets = []
        for i, t in enumerate(self.tasks):
            try:
                tw = TaskWidget(i, t)
                self.scroll_widget_layout.addWidget(tw)
                self.task_widgets.append(tw)
            except Exception as e:
                self.append_log(
                    f"❌ [ERROR] Failed to create TaskWidget {t.get('name','?')}: {e}\n"
                )

        self.scroll_widget_layout.addStretch(1)
        self.run_validator()
        self.append_log("✅ [INFO] Configuration refreshed and validated.\n")

    def run_validator(self):
        if hasattr(self, "validator") and self.validator.isRunning():
            self.validator.terminate()
            self.validator.wait()
        self.validator = ValidatorThread(self.tasks, self.log_path, self.signals)
        self.validator.start()
        self.append_log("\n🔄 [INFO] Ran Validations \n")


# ---------------------------- CONFIG LOADER -----------------------------------


def load_all_configs(folder: Path):
    merged = {"projectname": "", "os": platform.system().lower(), "tasks": []}
    current_os = platform.system().lower()
    json_files = list(folder.glob("*.json"))
    merged["projectname"] = "Merged Tasks" if len(json_files) > 1 else "Tasks"
    for file in folder.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                raw = f.read()
            try:
                cfg = json.loads(raw)
            except json.JSONDecodeError:
                cfg = json.loads(sanitize_json_like(raw))
            if isinstance(cfg, dict) and "tasks" in cfg:
                cfg_os = cfg.get("os", current_os).lower()
                if cfg_os != current_os:
                    continue
                for t in cfg.get("tasks", []):
                    if isinstance(t, dict):
                        tname = t.get("name", f"Task from {file.name}")
                        t["name"] = f"{file.stem}: {tname}"
                        merged["tasks"].append(t)
        except Exception as e:
            print(f"Could not read {file}: {e}")
    return merged


# ---------------------------- MAIN ENTRY --------------------------------------


def main():
    app = QApplication(sys.argv)
    cfg = load_all_configs(Path("."))
    w = MainWindow(cfg)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
