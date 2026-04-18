import os
import shutil
import threading
import time
import glob
from datetime import datetime
from tkinter import *
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

BACKUP_COOLDOWN_SEC = 2
FILE_WRITE_SLEEP_SEC = 0.5
DATE_FOLDER_FORMAT = "%Y-%m-%d"
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
LOG_TIME_FORMAT = "%H:%M:%S"

class BackupEngine:
    def __init__(self, log_callback: Callable[[str], None]):
        self.log_callback = log_callback
        self.monitoring = False
        self.stop_event = threading.Event()
        self.observer: Optional[Observer] = None
        self.monitor_thread: Optional[threading.Thread] = None

        self.last_backup_time = 0.0
        self.backup_cooldown = BACKUP_COOLDOWN_SEC

        self.source_pattern = ""          # can be a direct file or a pattern with $
        self.backup_base_dir = ""         # user selected base folder (for custom mode)
        self.location_type = "custom"     # "custom" or "script_dated"
        self.use_timestamp = True
        self.mode = "modification"        # "modification" or "time"
        self.time_interval_seconds = 300  # default 5 minutes

    def set_config(self, source: str, backup_base: str, location_type: str,
                   use_timestamp: bool, mode: str, interval_sec: int) -> None:
        self.source_pattern = source.strip()
        self.backup_base_dir = backup_base.strip() if backup_base else ""
        self.location_type = location_type
        self.use_timestamp = use_timestamp
        self.mode = mode
        self.time_interval_seconds = interval_sec

    def get_effective_backup_dir(self) -> str:
        date_str = datetime.now().strftime(DATE_FOLDER_FORMAT)
        if self.location_type == "script_dated":
            script_dir = os.path.dirname(os.path.abspath(__file__))
            folder = os.path.join(script_dir, f"Backup-{date_str}")
        else:
            if not self.backup_base_dir:
                return ""
            folder = os.path.join(self.backup_base_dir, f"Backup-{date_str}")
        os.makedirs(folder, exist_ok=True)
        return folder

    def resolve_source_file(self) -> Optional[str]:
        src = self.source_pattern
        directory = os.path.dirname(src)
        filename = os.path.basename(src)
        name, ext = os.path.splitext(filename)

        if "$" in name:
            prefix = name.split("$")[0]
            pattern = os.path.join(directory, f"{prefix}$*{ext}")
            matching = glob.glob(pattern)
            if not matching:
                self._log(f"ERROR: No matching save files for pattern: {pattern}")
                return None
            return max(matching, key=os.path.getmtime)
        else:
            return src if os.path.isfile(src) else None

    def perform_backup(self) -> bool:
        now = time.time()
        if now - self.last_backup_time < self.backup_cooldown:
            return False
        self.last_backup_time = now

        src = self.resolve_source_file()
        if not src:
            self._log("ERROR: Source file not set or does not exist.")
            return False

        dst_dir = self.get_effective_backup_dir()
        if not dst_dir:
            self._log("ERROR: Backup destination could not be determined.")
            return False

        base = os.path.basename(src)
        name, ext = os.path.splitext(base)
        if self.use_timestamp:
            ts = datetime.now().strftime(TIMESTAMP_FORMAT)
            dest_name = f"{name}_backup_{ts}{ext}"
        else:
            dest_name = base
        dest_path = os.path.join(dst_dir, dest_name)

        try:
            shutil.copy(src, dest_path)
            self._log(f"Backed up '{os.path.basename(src)}' -> {dest_path}")
            return True
        except Exception as e:
            self._log(f"Backup FAILED: {e}")
            return False

    def _log(self, msg: str) -> None:
        if self.log_callback:
            self.log_callback(msg)

    def start(self) -> bool:
        if self.monitoring:
            self._log("Monitoring already running.")
            return False

        if not self.source_pattern:
            self._log("ERROR: No source file set.")
            return False
        if self.location_type == "custom" and not self.backup_base_dir:
            self._log("ERROR: Custom base folder not set.")
            return False
        if self.mode == "modification" and not WATCHDOG_AVAILABLE:
            self._log("ERROR: Watchdog not installed. Use time‑based backup.")
            return False

        self.monitoring = True
        self.stop_event.clear()

        if self.mode == "modification":
            self._start_watchdog()
        else:
            self._start_timer()

        self._log(f"Monitoring started (mode: {self.mode})")
        return True

    def stop(self) -> None:
        if not self.monitoring:
            return
        self.monitoring = False
        self.stop_event.set()

        if self.observer:
            self.observer.stop()
            self.observer = None
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1)

        self._log("Monitoring stopped.")

    def _start_watchdog(self) -> None:
        src = self.source_pattern
        watch_dir = os.path.dirname(src)
        filename = os.path.basename(src)
        name, ext = os.path.splitext(filename)

        if "$" in name:
            prefix = name.split("$")[0]
        else:
            prefix = name

        class SpecificHandler(FileSystemEventHandler):
            def __init__(self, engine: BackupEngine, pfx: str, ext_str: str):
                self.engine = engine
                self.pfx = pfx
                self.ext = ext_str

            def _matches(self, path: str) -> bool:
                fname = os.path.basename(path)
                return fname.startswith(self.pfx + "$") and fname.endswith(self.ext)

            def on_created(self, event):
                if not event.is_directory and self._matches(event.src_path):
                    time.sleep(FILE_WRITE_SLEEP_SEC)
                    self.engine.perform_backup()

            def on_modified(self, event):
                if not event.is_directory and self._matches(event.src_path):
                    time.sleep(FILE_WRITE_SLEEP_SEC)
                    self.engine.perform_backup()

            def on_moved(self, event):
                if not event.is_directory and self._matches(event.dest_path):
                    time.sleep(FILE_WRITE_SLEEP_SEC)
                    self.engine.perform_backup()

        handler = SpecificHandler(self, prefix, ext)
        self.observer = Observer()
        self.observer.schedule(handler, watch_dir, recursive=False)
        self.observer.start()

    def _start_timer(self) -> None:
        def timer_loop():
            while not self.stop_event.wait(self.time_interval_seconds):
                if self.monitoring:
                    self.perform_backup()

        self.monitor_thread = threading.Thread(target=timer_loop, daemon=True)
        self.monitor_thread.start()


class BackupApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Game Save Backup Manager")
        self.root.geometry("500x400")
        self.root.resizable(True, True)

        self.engine = BackupEngine(log_callback=self.log)

        self.source_path = StringVar()
        self.backup_dir = StringVar()
        self.backup_mode = StringVar(value="modification")
        self.time_interval = IntVar(value=5)
        self.time_unit = StringVar(value="minutes")
        self.use_timestamp = BooleanVar(value=True)
        self.backup_location_type = StringVar(value="custom")

        self.create_widgets()
        self.log("Ready. Set the paths and click 'Start Monitoring'.")

    def create_widgets(self):
        main = ttk.Frame(self.root, padding="10")
        main.pack(fill=BOTH, expand=True)

        ttk.Label(main, text="Source Game Save File:").grid(row=0, column=0, sticky=W, pady=5)
        ttk.Entry(main, textvariable=self.source_path, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(main, text="Browse", command=self.browse_source).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(main, text="Backup Destination (Custom):").grid(row=1, column=0, sticky=W, pady=5)
        self.backup_entry = ttk.Entry(main, textvariable=self.backup_dir, width=50)
        self.backup_entry.grid(row=1, column=1, padx=5, pady=5)
        self.browse_btn = ttk.Button(main, text="Browse", command=self.browse_backup)
        self.browse_btn.grid(row=1, column=2, padx=5, pady=5)

        loc_frame = ttk.Frame(main)
        loc_frame.grid(row=2, column=0, columnspan=3, sticky=W, pady=5)
        ttk.Radiobutton(loc_frame, text="Use custom folder",
                        variable=self.backup_location_type, value="custom",
                        command=self.toggle_location).pack(side=LEFT, padx=5)
        ttk.Radiobutton(loc_frame, text="Auto in script path",
                        variable=self.backup_location_type, value="script_dated",
                        command=self.toggle_location).pack(side=LEFT, padx=5)

        mode_frame = ttk.LabelFrame(main, text="Backup Trigger", padding="5")
        mode_frame.grid(row=3, column=0, columnspan=3, sticky=EW, pady=10)

        ttk.Radiobutton(mode_frame, text="On file modification (watchdog)",
                        variable=self.backup_mode, value="modification").grid(row=0, column=0, sticky=W, padx=10)
        ttk.Radiobutton(mode_frame, text="Time‑based backup",
                        variable=self.backup_mode, value="time").grid(row=1, column=0, sticky=W, padx=10)

        self.time_frame = ttk.Frame(mode_frame)
        self.time_frame.grid(row=1, column=1, sticky=W, padx=20)
        ttk.Label(self.time_frame, text="Every").pack(side=LEFT)
        self.interval_spin = ttk.Spinbox(self.time_frame, from_=1, to=3600, width=5,
                                         textvariable=self.time_interval)
        self.interval_spin.pack(side=LEFT, padx=5)
        ttk.Combobox(self.time_frame, textvariable=self.time_unit,
                     values=["seconds", "minutes"], width=8, state="readonly").pack(side=LEFT)

        self.backup_mode.trace_add('write', self.toggle_time_controls)
        self.toggle_time_controls()

        ttk.Checkbutton(main, text="Add timestamp to backup filenames",
                        variable=self.use_timestamp).grid(row=4, column=0, columnspan=3, sticky=W, pady=5)

        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=5, column=0, columnspan=3, pady=10)
        self.start_btn = ttk.Button(btn_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_btn.pack(side=LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="Stop Monitoring", command=self.stop_monitoring, state=DISABLED)
        self.stop_btn.pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Backup Now (Manual)", command=self.perform_backup).pack(side=LEFT, padx=5)

        ttk.Label(main, text="Activity Log:").grid(row=6, column=0, sticky=W, pady=(10, 0))
        log_frame = ttk.Frame(main)
        log_frame.grid(row=7, column=0, columnspan=3, sticky=NSEW, pady=5)
        self.log_text = Text(log_frame, height=12, wrap=WORD, state=DISABLED)
        scrollbar = ttk.Scrollbar(log_frame, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        main.columnconfigure(1, weight=1)
        main.rowconfigure(7, weight=1)

        self.toggle_location()

    def toggle_location(self):
        if self.backup_location_type.get() == "custom":
            self.backup_entry.config(state=NORMAL)
            self.browse_btn.config(state=NORMAL)
        else:
            self.backup_entry.config(state=DISABLED)
            self.browse_btn.config(state=DISABLED)

    def toggle_time_controls(self, *args):
        state = NORMAL if self.backup_mode.get() == "time" else DISABLED
        for child in self.time_frame.winfo_children():
            child.configure(state=state)
        self.interval_spin.configure(state=state)

    def browse_source(self):
        path = filedialog.askopenfilename(title="Select game save file")
        if path:
            self.source_path.set(path)

    def browse_backup(self):
        folder = filedialog.askdirectory(title="Select custom backup base folder")
        if folder:
            os.makedirs(folder, exist_ok=True)
            self.backup_dir.set(folder)
            self.log(f"Custom base folder set to: {folder}")

    def log(self, message: str):
        timestamp = datetime.now().strftime(LOG_TIME_FORMAT)
        self.log_text.configure(state=NORMAL)
        self.log_text.insert(END, f"[{timestamp}] {message}\n")
        self.log_text.see(END)
        self.log_text.configure(state=DISABLED)
        self.root.update_idletasks()

    def perform_backup(self):
        self._sync_engine_config()
        self.engine.perform_backup()

    def start_monitoring(self):
        src = self.source_path.get().strip()
        if not src:
            messagebox.showerror("Error", "Please select a source save file.")
            return
        if not os.path.isfile(src) and "$" not in os.path.basename(src):
            messagebox.showerror("Error", f"Source file does not exist:\n{src}")
            return

        if self.backup_location_type.get() == "custom":
            base = self.backup_dir.get().strip()
            if not base:
                messagebox.showerror("Error", "Please select a custom backup base folder or switch to auto mode.")
                return

        interval = self.time_interval.get()
        unit = self.time_unit.get()
        interval_sec = interval * 60 if unit == "minutes" else interval

        self._sync_engine_config(interval_sec)

        if not self.engine.start():
            return

        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)

        effective = self.engine.get_effective_backup_dir()
        self.log(f"Backups will be stored in: {effective}")

    def _sync_engine_config(self, interval_sec: Optional[int] = None):
        if interval_sec is None:
            interval = self.time_interval.get()
            unit = self.time_unit.get()
            interval_sec = interval * 60 if unit == "minutes" else interval

        self.engine.set_config(
            source=self.source_path.get().strip(),
            backup_base=self.backup_dir.get().strip(),
            location_type=self.backup_location_type.get(),
            use_timestamp=self.use_timestamp.get(),
            mode=self.backup_mode.get(),
            interval_sec=interval_sec
        )

    def stop_monitoring(self):
        self.engine.stop()
        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)


if __name__ == "__main__":
    root = Tk()
    app = BackupApp(root)
    root.mainloop()