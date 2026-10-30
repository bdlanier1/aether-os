import sys
import json
import subprocess
import urllib.request
from collections import deque
from PySide6.QtWidgets import (
QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
QTabWidget, QLabel, QPushButton, QTextEdit, QLineEdit,
QComboBox, QGridLayout, QGroupBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from emulation_tab import EmulationTab


class CommandRunner(QThread):
output_ready = Signal(str)
task_finished = Signal(str, int)

def __init__(self, cmd_list, label):
    super().__init__()
    self.cmd_list = cmd_list
    self.label = label

def run(self):
    try:
        proc = subprocess.Popen(
            self.cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        for line in proc.stdout:
            self.output_ready.emit(line.rstrip())
        proc.wait()
        self.task_finished.emit(self.label, proc.returncode)
    except Exception as e:
        self.output_ready.emit(f"[ERROR] {e}")
        self.task_finished.emit(self.label, 1)


class OllamaWorker(QThread):
response_ready = Signal(str)
error_occurred = Signal(str)

def __init__(self, model: str, prompt: str):
    super().__init__()
    self.model = model
    self.prompt = prompt

def run(self):
    url = "http://127.0.0.1:11434/api/generate"
    payload = json.dumps({
        "model": self.model,
        "prompt": self.prompt,
        "stream": False
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.response_ready.emit(data.get("response", "No response received."))
    except Exception as e:
        self.error_occurred.emit(str(e))


class AetherHubWindow(QMainWindow):
def __init__(self):
    super().__init__()
    self.setWindowTitle("AetherOS Command & OmniAI Hub")
    self.resize(1100, 720)
    self.cmd_queue = deque()
    self.active_runner = None
    self.ollama_worker = None

    self._apply_dark_theme()
    self._init_ui()

    self.gpu_timer = QTimer(self)
    self.gpu_timer.timeout.connect(self.update_gpu_telemetry)
    self.gpu_timer.start(3000)
    self.update_gpu_telemetry()

def _apply_dark_theme(self):
    self.setStyleSheet("""
        QMainWindow, QWidget { background-color: #0F172A; color: #F8FAFC; font-family: 'Inter', sans-serif; }
        QTabWidget::pane { border: 1px solid #1E293B; border-radius: 6px; }
        QTabBar::tab { background: #1E293B; color: #94A3B8; padding: 10px 18px; margin-right: 4px; border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: bold; }
        QTabBar::tab:selected { background: #2563EB; color: #FFFFFF; }
        QPushButton { background-color: #1E293B; color: #F8FAFC; border: 1px solid #334155; padding: 8px 14px; border-radius: 6px; }
        QPushButton:hover { background-color: #334155; }
        QLineEdit, QTextEdit, QComboBox, QTreeWidget { background-color: #1E293B; color: #F8FAFC; border: 1px solid #334155; border-radius: 6px; padding: 6px; }
        QGroupBox { border: 1px solid #334155; border-radius: 6px; margin-top: 12px; padding-top: 10px; font-weight: bold; }
    """)

def _init_ui(self):
    central = QWidget()
    self.setCentralWidget(central)
    main_layout = QVBoxLayout(central)

    header = QHBoxLayout()
    brand = QLabel("⚡ AETHER OS // COMMAND HUB")
    brand.setStyleSheet("font-size: 22px; font-weight: bold; color: #38BDF8;")
    header.addWidget(brand)
    header.addStretch()

    self.gpu_label = QLabel("NVIDIA GPU: Detecting...")
    self.gpu_label.setStyleSheet("color: #10B981; font-weight: bold;")
    header.addWidget(self.gpu_label)
    main_layout.addLayout(header)

    self.tabs = QTabWidget()
    self.tabs.addTab(self._build_dashboard_tab(), "🚀 Suite Launcher & System")
    self.tabs.addTab(self._build_ai_tab(), "🧠 OmniAI (Local Ollama)")
    self.emulation_tab = EmulationTab(self)
    self.tabs.addTab(self.emulation_tab, "🕹️ Emulation & ROMs")
    main_layout.addWidget(self.tabs)

    self.console_out = QTextEdit()
    self.console_out.setReadOnly(True)
    self.console_out.setFixedHeight(130)
    self.console_out.setPlaceholderText("System task queue & telemetry logs will appear here...")
    main_layout.addWidget(self.console_out)

def _build_dashboard_tab(self):
    tab = QWidget()
    layout = QVBoxLayout(tab)

    apps_group = QGroupBox("Quick Launch Suite (Flatpak)")
    grid = QGridLayout(apps_group)

    suites = [
        ("🌐 Firefox", ["flatpak", "run", "org.mozilla.firefox"]),
        ("🦁 Brave Browser", ["flatpak", "run", "com.brave.Browser"]),
        ("📄 LibreOffice", ["flatpak", "run", "org.libreoffice.LibreOffice"]),
        ("📓 Obsidian", ["flatpak", "run", "md.obsidian.Obsidian"]),
        ("🎨 Krita Studio", ["flatpak", "run", "org.kde.krita"]),
        ("🖼️ GIMP Editor", ["flatpak", "run", "org.gimp.GIMP"]),
        ("🎬 Kdenlive Video", ["flatpak", "run", "org.kde.kdenlive"]),
        ("🎥 OBS Studio", ["flatpak", "run", "com.obsproject.Studio"]),
        ("🎮 Steam", ["flatpak", "run", "com.valvesoftware.Steam"]),
        ("🕹️ RetroArch", ["flatpak", "run", "org.libretro.RetroArch"]),
    ]

    for idx, (label, cmd) in enumerate(suites):
        btn = QPushButton(label)
        btn.clicked.connect(lambda _, c=cmd: subprocess.Popen(c, start_new_session=True))
        grid.addWidget(btn, idx // 5, idx % 5)

    layout.addWidget(apps_group)

    maint_group = QGroupBox("AetherOS System Maintenance Queue")
    maint_layout = QHBoxLayout(maint_group)

    btn_first_boot = QPushButton("Run First-Boot Provisioner")
    btn_first_boot.clicked.connect(lambda: self.enqueue_command(["/usr/bin/aether-first-boot"], "First-Boot Provisioning"))
    maint_layout.addWidget(btn_first_boot)

    btn_update_fp = QPushButton("Update All Flatpaks")
    btn_update_fp.clicked.connect(lambda: self.enqueue_command(["flatpak", "update", "-y"], "Flatpak System Update"))
    maint_layout.addWidget(btn_update_fp)

    btn_ostree = QPushButton("Update Base OS (rpm-ostree)")
    btn_ostree.clicked.connect(lambda: self.enqueue_command(["rpm-ostree", "upgrade"], "OS Image Upgrade"))
    maint_layout.addWidget(btn_ostree)

    layout.addWidget(maint_group)
    layout.addStretch()
    return tab

def _build_ai_tab(self):
    tab = QWidget()
    layout = QVBoxLayout(tab)

    top_bar = QHBoxLayout()
    top_bar.addWidget(QLabel("Active Local Model:"))
    self.model_combo = QComboBox()
    self.model_combo.addItems(["llama3.1:8b", "qwen2.5-coder:7b", "mistral:7b", "deepseek-r1:8b"])
    top_bar.addWidget(self.model_combo, stretch=1)

    btn_pull = QPushButton("⬇ Pull Selected Model")
    btn_pull.clicked.connect(lambda: self.enqueue_command(["ollama", "pull", self.model_combo.currentText()], f"Pull {self.model_combo.currentText()}"))
    top_bar.addWidget(btn_pull)
    layout.addLayout(top_bar)

    self.chat_history = QTextEdit()
    self.chat_history.setReadOnly(True)
    layout.addWidget(self.chat_history)

    prompt_bar = QHBoxLayout()
    self.prompt_input = QLineEdit()
    self.prompt_input.setPlaceholderText("Ask your local NVIDIA-accelerated LLM anything...")
    self.prompt_input.returnPressed.connect(self.send_ollama_prompt)
    prompt_bar.addWidget(self.prompt_input, stretch=1)

    self.btn_send = QPushButton("Send")
    self.btn_send.setStyleSheet("background-color: #2563EB; font-weight: bold;")
    self.btn_send.clicked.connect(self.send_ollama_prompt)
    prompt_bar.addWidget(self.btn_send)
    layout.addLayout(prompt_bar)

    return tab

def send_ollama_prompt(self):
    prompt = self.prompt_input.text().strip()
    if not prompt or (self.ollama_worker and self.ollama_worker.isRunning()):
        return

    model = self.model_combo.currentText()
    self.prompt_input.clear()
    self.btn_send.setEnabled(False)
    self.chat_history.append(f"<b>You:</b> {prompt}")

    self.ollama_worker = OllamaWorker(model, prompt)
    self.ollama_worker.response_ready.connect(self._on_ollama_reply)
    self.ollama_worker.error_occurred.connect(self._on_ollama_error)
    self.ollama_worker.start()

def _on_ollama_reply(self, text: str):
    self.chat_history.append(f"<b>OmniAI ({self.model_combo.currentText()}):</b> {text}<hr>")
    self.btn_send.setEnabled(True)

def _on_ollama_error(self, err: str):
    self.chat_history.append(f"<span style='color:#EF4444;'><b>Ollama Error:</b> {err} (Ensure ollama.service is running and model is pulled)</span><hr>")
    self.btn_send.setEnabled(True)

def enqueue_command(self, cmd_list: list, label: str):
    self.cmd_queue.append((cmd_list, label))
    self.console_out.append(f"[QUEUE] Added task: {label}")
    self._process_next_command()

def _process_next_command(self):
    if self.active_runner and self.active_runner.isRunning():
        return
    if not self.cmd_queue:
        return

    cmd_list, label = self.cmd_queue.popleft()
    self.console_out.append(f"▶ Starting: {label} ({' '.join(cmd_list)})")
    self.active_runner = CommandRunner(cmd_list, label)
    self.active_runner.output_ready.connect(self.console_out.append)
    self.active_runner.task_finished.connect(self._on_command_finished)
    self.active_runner.start()

def _on_command_finished(self, label: str, code: int):
    status = "COMPLETED" if code == 0 else f"FAILED (exit {code})"
    self.console_out.append(f"✔ [{status}] {label}\n")
    self._process_next_command()

def update_gpu_telemetry(self):
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        name, temp, util, mem_used, mem_tot = [x.strip() for x in out.split(",")]
        self.gpu_label.setText(f"🟢 {name} | {temp}°C | Load: {util}% | VRAM: {mem_used}/{mem_tot} MB")
    except Exception:
        self.gpu_label.setText("⚪ NVIDIA Telemetry: Offline / Nouveau")


if __name__ == "__main__":
app = QApplication(sys.argv)
win = AetherHubWindow()
win.show()
sys.exit(app.exec())
