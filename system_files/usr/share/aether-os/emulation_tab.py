import os
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (
QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
QLineEdit, QComboBox, QTreeWidget, QTreeWidgetItem,
QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal

CORE_MAPPING = {
"snes": {"name": "Super Nintendo (SNES)", "core": "snes9x_libretro.so", "exts": {".sfc", ".smc", ".zip", ".7z"}},
"nes": {"name": "Nintendo (NES)", "core": "mesen_libretro.so", "exts": {".nes", ".zip", ".7z"}},
"gba": {"name": "Game Boy Advance", "core": "mgba_libretro.so", "exts": {".gba", ".agb", ".zip", ".7z"}},
"genesis": {"name": "Sega Genesis", "core": "genesis_plus_gx_libretro.so", "exts": {".md", ".gen", ".bin", ".zip", ".7z"}},
"psx": {"name": "PlayStation (PS1)", "core": "beetle_psx_hw_libretro.so", "exts": {".cue", ".chd", ".iso", ".pbp", ".m3u"}},
"n64": {"name": "Nintendo 64", "core": "mupen64plus_next_libretro.so", "exts": {".n64", ".z64", ".v64", ".zip"}},
"psp": {"name": "PlayStation Portable", "core": "ppsspp_libretro.so", "exts": {".iso", ".cso", ".pbp"}},
"arcade": {"name": "Arcade (FBNeo)", "core": "fbneo_libretro.so", "exts": {".zip", ".7z"}}
}

FLATPAK_CORE_DIR = os.path.expanduser("~/.var/app/org.libretro.RetroArch/config/retroarch/cores")


class RomScannerWorker(QThread):
finished = Signal(list)

def __init__(self, base_rom_dir: Path):
    super().__init__()
    self.base_rom_dir = base_rom_dir

def run(self):
    found_roms = []
    if not self.base_rom_dir.exists():
        self.finished.emit(found_roms)
        return

    for sys_key, sys_data in CORE_MAPPING.items():
        sys_dir = self.base_rom_dir / sys_key
        if not sys_dir.exists():
            continue
        for root, _, files in os.walk(sys_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in sys_data["exts"]:
                    full_path = os.path.join(root, file)
                    try:
                        size_mb = os.path.getsize(full_path) / (1024 * 1024)
                    except OSError:
                        size_mb = 0.0
                    found_roms.append({
                        "title": os.path.splitext(file)[0],
                        "system_key": sys_key,
                        "system_name": sys_data["name"],
                        "core": sys_data["core"],
                        "path": full_path,
                        "size": f"{size_mb:.2f} MB"
                    })
    found_roms.sort(key=lambda x: x["title"].lower())
    self.finished.emit(found_roms)


class EmulationTab(QWidget):
def __init__(self, parent=None):
    super().__init__(parent)
    self.rom_dir = Path.home() / "Emulation" / "roms"
    self.bios_dir = Path.home() / "Emulation" / "bios"
    self.all_roms = []
    self.scanner_thread = None

    self._ensure_directories()
    self._init_ui()
    self.refresh_library()

def _ensure_directories(self):
    self.bios_dir.mkdir(parents=True, exist_ok=True)
    for sys_key in CORE_MAPPING.keys():
        (self.rom_dir / sys_key).mkdir(parents=True, exist_ok=True)

def _init_ui(self):
    layout = QVBoxLayout(self)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(12)

    header_layout = QHBoxLayout()
    title_label = QLabel("RetroArch Emulation Hub")
    title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #00E5FF;")
    header_layout.addWidget(title_label)
    header_layout.addStretch()

    btn_open_folder = QPushButton("Open ROMs Folder")
    btn_open_folder.clicked.connect(lambda: subprocess.Popen(["xdg-open", str(self.rom_dir)]))
    header_layout.addWidget(btn_open_folder)

    btn_launch_ra = QPushButton("Launch RetroArch UI")
    btn_launch_ra.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 6px 14px;")
    btn_launch_ra.clicked.connect(self.launch_standalone_retroarch)
    header_layout.addWidget(btn_launch_ra)
    layout.addLayout(header_layout)

    filter_layout = QHBoxLayout()
    self.search_input = QLineEdit()
    self.search_input.setPlaceholderText("Search ROMs by title...")
    self.search_input.textChanged.connect(self.apply_filters)
    filter_layout.addWidget(self.search_input, stretch=3)

    self.system_filter = QComboBox()
    self.system_filter.addItem("All Systems", "all")
    for sys_key, sys_data in CORE_MAPPING.items():
        self.system_filter.addItem(sys_data["name"], sys_key)
    self.system_filter.currentIndexChanged.connect(self.apply_filters)
    filter_layout.addWidget(self.system_filter, stretch=1)

    self.btn_scan = QPushButton("Rescan Library")
    self.btn_scan.clicked.connect(self.refresh_library)
    filter_layout.addWidget(self.btn_scan)
    layout.addLayout(filter_layout)

    self.rom_tree = QTreeWidget()
    self.rom_tree.setHeaderLabels(["Game Title", "System", "Assigned Libretro Core", "Size"])
    self.rom_tree.setAlternatingRowColors(True)
    self.rom_tree.setRootIsDecorated(False)
    self.rom_tree.setSortingEnabled(True)
    self.rom_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
    self.rom_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    self.rom_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
    self.rom_tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
    self.rom_tree.itemDoubleClicked.connect(self.launch_selected_rom)
    layout.addWidget(self.rom_tree)

    footer_layout = QHBoxLayout()
    self.status_label = QLabel("Ready.")
    self.status_label.setStyleSheet("color: #9CA3AF;")
    footer_layout.addWidget(self.status_label)
    footer_layout.addStretch()

    btn_play = QPushButton("▶ Launch Selected Game")
    btn_play.setStyleSheet("background-color: #10B981; color: #FFFFFF; font-size: 14px; font-weight: bold; padding: 8px 20px; border-radius: 6px;")
    btn_play.clicked.connect(self.launch_selected_rom)
    footer_layout.addWidget(btn_play)
    layout.addLayout(footer_layout)

def refresh_library(self):
    if self.scanner_thread and self.scanner_thread.isRunning():
        return
    self.btn_scan.setEnabled(False)
    self.status_label.setText(f"Scanning {self.rom_dir}...")
    self.scanner_thread = RomScannerWorker(self.rom_dir)
    self.scanner_thread.finished.connect(self._on_scan_finished)
    self.scanner_thread.start()

def _on_scan_finished(self, rom_list: list):
    self.all_roms = rom_list
    self.btn_scan.setEnabled(True)
    self.apply_filters()

def apply_filters(self):
    query = self.search_input.text().strip().lower()
    selected_sys = self.system_filter.currentData()
    self.rom_tree.setSortingEnabled(False)
    self.rom_tree.clear()

    visible_count = 0
    for rom in self.all_roms:
        if selected_sys != "all" and rom["system_key"] != selected_sys:
            continue
        if query and query not in rom["title"].lower():
            continue
        item = QTreeWidgetItem([rom["title"], rom["system_name"], rom["core"], rom["size"]])
        item.setData(0, Qt.UserRole, rom)
        self.rom_tree.addTopLevelItem(item)
        visible_count += 1

    self.rom_tree.setSortingEnabled(True)
    self.status_label.setText(f"Showing {visible_count} of {len(self.all_roms)} ROMs in ~/Emulation/roms")

def launch_selected_rom(self):
    selected_items = self.rom_tree.selectedItems()
    if not selected_items:
        QMessageBox.information(self, "No Game Selected", "Please select a ROM from the list to launch.")
        return

    rom_data = selected_items[0].data(0, Qt.UserRole)
    core_path = os.path.join(FLATPAK_CORE_DIR, rom_data["core"])
    rom_path = rom_data["path"]

    if not os.path.exists(core_path):
        reply = QMessageBox.question(
            self, "Core Not Found Locally",
            f"The Libretro core '{rom_data['core']}' was not found in:\n{FLATPAK_CORE_DIR}\n\n"
            "Open RetroArch's Online Updater to download it now?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.launch_standalone_retroarch()
        return

    cmd = ["flatpak", "run", "--filesystem=host", "org.libretro.RetroArch", "-L", core_path, rom_path]
    try:
        self.status_label.setText(f"Launching {rom_data['title']}...")
        subprocess.Popen(cmd, start_new_session=True)
    except Exception as e:
        QMessageBox.critical(self, "Launch Failed", f"Failed to execute RetroArch:\n{e}")

def launch_standalone_retroarch(self):
    try:
        subprocess.Popen(["flatpak", "run", "org.libretro.RetroArch"], start_new_session=True)
    except Exception as e:
        QMessageBox.critical(self, "Launch Error", f"Could not launch RetroArch:\n{e}")
