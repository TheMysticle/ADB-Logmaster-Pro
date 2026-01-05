import customtkinter as ctk
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, Menu, messagebox, simpledialog
import queue
from collections import deque
import shutil 
import sys
import os
import re
import time

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

MAX_BUFFER = 50000 
APP_SIZE = "1150x800"

# Expanded Colors
COLORS = {
    "FATAL": "#FF3333", 
    "ERROR": "#FF5555", 
    "WARN":  "#FFB86C", 
    "INFO":  "#50FA7B", 
    "DEBUG": "#8BE9FD", 
    "VERBOSE": "#BD93F9", 
    "DEFAULT": "#F8F8F2",
    "HEADER": "#F1C40F"
}

class ADBLoggerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ADB Logmaster Pro")
        self.geometry(APP_SIZE)
        
        # --- State ---
        self.logging_process = None
        self.scrcpy_process = None
        self.is_logging = False
        self.stop_event = threading.Event()
        self.input_queue = queue.Queue()
        self.log_buffer = deque(maxlen=MAX_BUFFER) 
        self.filter_text = ""
        self.auto_scroll_enabled = True 
        
        # Explorer State
        self.current_path = "/"
        self.selected_item = None
        
        # Sensor Data Storage
        self.cached_sensors = [] 
        self.show_decimal_ids = True 
        self.search_timer = None 
        
        # UI Cache
        self.sensor_ui_map = {} 
        self.build_queue = [] 
        self.lbl_sensor_count = None

        # --- UI Grid ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ================= SIDEBAR =================
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(20, weight=1)

        ctk.CTkLabel(self.sidebar, text="ADB Logmaster", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))

        self.device_menu = ctk.CTkOptionMenu(self.sidebar, values=["Scanning..."])
        self.device_menu.grid(row=2, column=0, padx=20, pady=(0, 10))

        self.log_type_var = ctk.StringVar(value="Logcat")
        self.log_type_seg = ctk.CTkSegmentedButton(self.sidebar, values=["Logcat", "Dmesg"], 
                                                   variable=self.log_type_var, command=self.on_mode_switch)
        self.log_type_seg.grid(row=3, column=0, padx=20, pady=(0, 10))

        self.use_root_var = ctk.BooleanVar(value=False)
        self.chk_root = ctk.CTkCheckBox(self.sidebar, text="Use Root (su)", variable=self.use_root_var)
        self.chk_root.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="w")

        self.btn_start = ctk.CTkButton(self.sidebar, text="Start Logging", fg_color="#2ecc71", hover_color="#27ae60", command=self.toggle_logging)
        self.btn_start.grid(row=5, column=0, padx=20, pady=5)
        
        self.btn_stop_clear = ctk.CTkButton(self.sidebar, text="⛔ Stop & Clear", fg_color="#c0392b", hover_color="#922b21", command=self.stop_and_clear)
        self.btn_stop_clear.grid(row=6, column=0, padx=20, pady=5)

        self.btn_refresh = ctk.CTkButton(self.sidebar, text="Refresh Devices", command=self.refresh_devices, fg_color="transparent", border_width=2)
        self.btn_refresh.grid(row=7, column=0, padx=20, pady=5)

        self.btn_save = ctk.CTkButton(self.sidebar, text="Save Filtered", command=self.save_log)
        self.btn_save.grid(row=8, column=0, padx=20, pady=5)

        # --- TOOLS MENU ---
        self.stats_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.stats_frame.grid(row=12, column=0, padx=10, pady=(20, 0), sticky="ew")
        
        ctk.CTkLabel(self.stats_frame, text="Advanced Tools", font=("Arial", 12, "bold"), text_color="gray").pack(anchor="w", padx=5)
        self.stats_grid = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        self.stats_grid.pack(fill="x", pady=5)

        def mk_btn(parent, txt, cmd, r, c, col):
            b = ctk.CTkButton(parent, text=txt, command=cmd, width=95, height=28, fg_color=col, font=("Arial", 11, "bold"))
            b.grid(row=r, column=c, padx=3, pady=3)

        mk_btn(self.stats_grid, "Battery", lambda: self.dump_stat("batterystats"), 0, 0, "#16a085")
        mk_btn(self.stats_grid, "Memory", lambda: self.dump_stat("meminfo"), 0, 1, "#16a085")
        
        btn_explorer = ctk.CTkButton(self.stats_grid, text="📁 Root File Explorer", command=self.init_file_explorer, 
                                    width=200, height=32, fg_color="#2980b9", font=("Arial", 11, "bold"))
        btn_explorer.grid(row=1, column=0, columnspan=2, padx=3, pady=5)

        btn_sensors = ctk.CTkButton(self.stats_grid, text="🔍 Sensor Analyzer", command=self.init_sensor_analyzer, 
                                    width=200, height=28, fg_color="#d35400", font=("Arial", 11, "bold"))
        btn_sensors.grid(row=2, column=0, columnspan=2, padx=3, pady=3)

        self.btn_scrcpy = ctk.CTkButton(self.sidebar, text="🚀 Launch Screen", fg_color="#9b59b6", hover_color="#8e44ad", command=self.toggle_scrcpy)
        self.btn_scrcpy.grid(row=15, column=0, padx=20, pady=(30, 5))

        self.status_label = ctk.CTkLabel(self.sidebar, text="Status: Idle", text_color="gray")
        self.status_label.grid(row=20, column=0, padx=20, pady=10)

        # ================= MAIN LOG AREA =================
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_rowconfigure(2, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Type to filter logs...")
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 5))
        self.search_entry.bind("<KeyRelease>", self.on_search_change)

        self.filter_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.filter_frame.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        
        filters = [("AVC Denial", "avc:  denied", "#c0392b"), ("Permission", "permission", "#d35400"), ("Error", "error", "#c0392b"), ("Clear Filter", "", "#7f8c8d")]
        for text, term, color in filters:
            ctk.CTkButton(self.filter_frame, text=text, height=24, width=80, fg_color=color, font=("Arial", 11), command=lambda t=term: self.quick_filter(t)).pack(side="left", padx=(0, 5))

        self.text_frame = ctk.CTkFrame(self.main_frame)
        self.text_frame.grid(row=2, column=0, sticky="nsew")
        self.text_frame.grid_rowconfigure(0, weight=1)
        self.text_frame.grid_columnconfigure(0, weight=1)

        self.textbox = tk.Text(self.text_frame, bg="#1a1a1a", fg="#dcdcdc", font=("Consolas", 11), bd=0, highlightthickness=0)
        self.textbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.scrollbar = ctk.CTkScrollbar(self.text_frame, command=self.textbox.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.textbox.configure(yscrollcommand=self.scrollbar.set)
        
        for tag, color in COLORS.items(): self.textbox.tag_config(tag, foreground=color)
        self.textbox.tag_config("HEADER", foreground="#F1C40F", font=("Consolas", 12, "bold"))

        self.refresh_devices()
        self._auto_refresh_devices_loop()
        self.update_loop()

    # ================= ROOT FILE EXPLORER =================
    def init_file_explorer(self):
        device = self.device_menu.get()
        if device in ["No devices", "Scanning...", "ADB Not Found"]: 
            messagebox.showerror("Error", "No device connected.")
            return

        self.exp_win = ctk.CTkToplevel(self)
        self.exp_win.title(f"Root Explorer - {device}")
        self.exp_win.geometry("900x600")
        self.exp_win.grid_columnconfigure(0, weight=1)
        self.exp_win.grid_rowconfigure(1, weight=1)
        self.exp_win.attributes("-topmost", True)

        nav_frame = ctk.CTkFrame(self.exp_win)
        nav_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(nav_frame, text="UP ⬆️", width=60, command=self._exp_go_up).pack(side="left", padx=5)
        self.path_entry = ctk.CTkEntry(nav_frame)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.path_entry.bind("<Return>", lambda e: self._exp_load_path(self.path_entry.get()))
        ctk.CTkButton(nav_frame, text="Refresh", width=70, command=lambda: self._exp_load_path(self.current_path)).pack(side="left", padx=5)

        self.exp_scroll = ctk.CTkScrollableFrame(self.exp_win)
        self.exp_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        action_frame = ctk.CTkFrame(self.exp_win)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(action_frame, text="+ File", width=90, fg_color="#27ae60", command=self._exp_create_file).pack(side="left", padx=5)
        ctk.CTkButton(action_frame, text="+ Folder", width=90, fg_color="#27ae60", command=self._exp_create_dir).pack(side="left", padx=5)
        ctk.CTkButton(action_frame, text="🗑️ Delete", width=90, fg_color="#c0392b", command=self._exp_delete_item).pack(side="right", padx=5)
        ctk.CTkButton(action_frame, text="ℹ️ Properties", width=90, command=self._exp_show_props).pack(side="right", padx=5)

        self._exp_load_path("/")

    def _adb_shell_cmd(self, cmd_str):
        device = self.device_menu.get()
        use_root = self.use_root_var.get()
        # Escaping for shell
        cmd_str = cmd_str.replace("'", "'\\''")
        full_cmd = ["adb", "-s", device, "shell"]
        if use_root: full_cmd.extend(["su", "-c", f"'{cmd_str}'"])
        else: full_cmd.append(cmd_str)
        try:
            res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=10)
            return res.stdout, res.stderr
        except Exception as e: return "", str(e)

    def _exp_load_path(self, path):
        # Cleaning path
        if not path.startswith("/"): path = "/" + path
        path = re.sub(r'/+', '/', path) # Remove double slashes
        if not path.endswith("/") and path != "/": path += "/"
        
        self.current_path = path
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, self.current_path)
        
        for widget in self.exp_scroll.winfo_children(): widget.destroy()
        self.selected_item = None

        # Using -la because -F often fails on stripped Android builds
        out, err = self._adb_shell_cmd(f"ls -la '{self.current_path}'")
        
        if err and "not found" in err.lower():
            # Try without -a if -la fails
            out, err = self._adb_shell_cmd(f"ls -l '{self.current_path}'")

        if not out and err:
            ctk.CTkLabel(self.exp_scroll, text=f"Error: {err.strip()}", text_color="#e74c3c").pack(pady=20)
            return

        lines = out.splitlines()
        found = False
        for line in lines:
            line = line.strip()
            if not line or line.startswith("total "): continue
            
            parts = line.split()
            if len(parts) < 4: continue
            
            # The filename is the last part. We detect types via the first char of the line.
            perms = parts[0]
            name = parts[-1]
            if name in [".", ".."]: continue

            # Indicator logic
            is_dir = perms.startswith('d')
            is_link = perms.startswith('l')
            
            icon = "📁" if is_dir else ("🔗" if is_link else "📄")
            color = "#3498db" if (is_dir or is_link) else "#bdc3c7"
            
            # Metadata for properties
            owner = parts[2] if len(parts) > 2 else "unknown"
            size = parts[4] if len(parts) > 4 else "0"

            item_btn = ctk.CTkButton(self.exp_scroll, text=f"{icon}  {name}", 
                                     anchor="w", fg_color="transparent", text_color=color,
                                     hover_color="#2c3e50", height=28)
            item_btn.pack(fill="x", pady=1)
            found = True

            # Use local variables in lambda to avoid closure issues
            def cmd_select(n=name, p=perms, s=size, o=owner, b=item_btn):
                self._exp_select(n, p, s, o, b)
            
            def cmd_enter(n=name):
                self._exp_load_path(self.current_path + n)

            item_btn.bind("<Button-1>", lambda e, f=cmd_select: f())
            if is_dir or is_link:
                item_btn.bind("<Double-Button-1>", lambda e, f=cmd_enter: f())

        if not found:
            ctk.CTkLabel(self.exp_scroll, text=" ( Empty or Restricted Directory ) ", text_color="gray").pack(pady=10)

    def _exp_select(self, name, perms, size, owner, btn):
        for child in self.exp_scroll.winfo_children():
            if isinstance(child, ctk.CTkButton): child.configure(fg_color="transparent")
        btn.configure(fg_color="#34495e")
        self.selected_item = {"name": name, "perms": perms, "size": size, "owner": owner}

    def _exp_go_up(self):
        if self.current_path == "/": return
        parts = self.current_path.rstrip("/").split("/")
        parent = "/".join(parts[:-1])
        self._exp_load_path(parent if parent else "/")

    def _exp_create_file(self):
        name = simpledialog.askstring("New File", "Enter filename:")
        if name:
            self._adb_shell_cmd(f"touch '{self.current_path}{name}'")
            self._exp_load_path(self.current_path)

    def _exp_create_dir(self):
        name = simpledialog.askstring("New Folder", "Enter folder name:")
        if name:
            self._adb_shell_cmd(f"mkdir -p '{self.current_path}{name}'")
            self._exp_load_path(self.current_path)

    def _exp_delete_item(self):
        if not self.selected_item: return
        target = self.current_path + self.selected_item['name']
        if messagebox.askyesno("Confirm", f"Delete {target}?\nThis is permanent."):
            self._adb_shell_cmd(f"rm -rf '{target}'")
            self._exp_load_path(self.current_path)

    def _exp_show_props(self):
        if not self.selected_item: return
        item = self.selected_item
        full = self.current_path + item['name']
        
        prop_win = ctk.CTkToplevel(self.exp_win)
        prop_win.title("Properties")
        prop_win.geometry("400x380")
        prop_win.attributes("-topmost", True)
        
        ctk.CTkLabel(prop_win, text=f"Object: {item['name']}", font=("Arial", 14, "bold")).pack(pady=10)
        ctk.CTkLabel(prop_win, text=f"Path: {full}", wraplength=350, text_color="gray").pack()
        ctk.CTkLabel(prop_win, text=f"Size: {item['size']} bytes").pack(pady=2)
        ctk.CTkLabel(prop_win, text=f"Current Perms: {item['perms']}").pack(pady=2)
        
        ctk.CTkLabel(prop_win, text="Chmod (Octal):", font=("Arial", 11, "bold")).pack(pady=(15, 0))
        entry = ctk.CTkEntry(prop_win, width=100, justify="center")
        entry.insert(0, "755")
        entry.pack(pady=5)
        
        def apply():
            mode = entry.get()
            if mode.isdigit():
                _, err = self._adb_shell_cmd(f"chmod {mode} '{full}'")
                if err: messagebox.showerror("Error", err)
                else: 
                    messagebox.showinfo("Success", "Permissions changed.")
                    prop_win.destroy()
                    self._exp_load_path(self.current_path)

        ctk.CTkButton(prop_win, text="Set Permissions", command=apply, fg_color="#16a085").pack(pady=20)

    # ================= DEVICE / LOGGING / SENSORS (UNCHANGED CORE) =================
    def _auto_refresh_devices_loop(self):
        if not self.is_logging: self.refresh_devices(silent=True)
        self.after(3000, self._auto_refresh_devices_loop)

    def init_sensor_analyzer(self):
        device = self.device_menu.get()
        if device in ["No devices", "Scanning..."]: return
        self.sensor_win = ctk.CTkToplevel(self)
        self.sensor_win.title("Sensor Analyzer")
        self.sensor_win.geometry("800x600")
        self.sensor_scroll = ctk.CTkScrollableFrame(self.sensor_win)
        self.sensor_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        threading.Thread(target=self._fetch_sensors_thread, args=(device,), daemon=True).start()

    def _fetch_sensors_thread(self, device):
        try:
            out = subprocess.check_output(["adb", "-s", device, "shell", "dumpsys", "sensorservice"], text=True, errors='ignore')
            for line in out.splitlines()[:100]: # Showing subset for speed
                if ")" in line:
                    self.after(0, lambda l=line: ctk.CTkLabel(self.sensor_scroll, text=l, anchor="w").pack(fill="x"))
        except: pass

    def toggle_scrcpy(self):
        if self.scrcpy_process and self.scrcpy_process.poll() is None:
            self.scrcpy_process.terminate()
        else: self.launch_scrcpy()

    def launch_scrcpy(self):
        device = self.device_menu.get()
        if device in ["No devices"]: return
        self.scrcpy_process = subprocess.Popen(["scrcpy", "-s", device, "--max-size", "800"])

    def dump_stat(self, service):
        device = self.device_menu.get()
        if device in ["No devices"]: return
        threading.Thread(target=lambda: self.input_queue.put((self._adb_shell_cmd(f"dumpsys {service}")[0], "DEFAULT")), daemon=True).start()

    def refresh_devices(self, silent=False):
        try:
            res = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            devs = [l.split("\t")[0] for l in res.stdout.strip().split("\n")[1:] if "\tdevice" in l]
            if devs:
                self.device_menu.configure(values=devs)
                if self.device_menu.get() not in devs: self.device_menu.set(devs[0])
            else: self.device_menu.configure(values=["No devices"])
        except: pass

    def toggle_logging(self):
        if not self.is_logging: self.start_logging()
        else: self.stop_logging()

    def start_logging(self):
        device = self.device_menu.get()
        if device == "No devices": return
        self.is_logging = True
        self.btn_start.configure(text="Stop Logging", fg_color="#e67e22")
        threading.Thread(target=self.adb_reader_thread, args=(device,), daemon=True).start()

    def stop_logging(self):
        self.is_logging = False
        if self.logging_process: self.logging_process.terminate()
        self.btn_start.configure(text="Start Logging", fg_color="#2ecc71")

    def adb_reader_thread(self, device):
        cmd = ["adb", "-s", device, "logcat", "-v", "threadtime"]
        self.logging_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
        for line in iter(self.logging_process.stdout.readline, ''):
            if not self.is_logging: break
            self.input_queue.put((line, "DEFAULT"))

    def update_loop(self):
        while not self.input_queue.empty():
            line, tag = self.input_queue.get()
            self.log_buffer.append((line, tag))
            if not self.filter_text or self.filter_text in line.lower():
                self.textbox.configure(state="normal")
                self.textbox.insert("end", line, tag)
                self.textbox.see("end")
                self.textbox.configure(state="disabled")
        self.after(50, self.update_loop)

    def on_search_change(self, e=None):
        self.filter_text = self.search_entry.get().lower()
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        for line, tag in self.log_buffer:
            if not self.filter_text or self.filter_text in line.lower():
                self.textbox.insert("end", line, tag)
        self.textbox.configure(state="disabled")

    def quick_filter(self, t):
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, t)
        self.on_search_change()

    def stop_and_clear(self):
        self.stop_logging()
        self.log_buffer.clear()
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")

    def save_log(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt")
        if path:
            with open(path, "w") as f: f.write(self.textbox.get("1.0", "end"))

    def on_mode_switch(self, v): self.stop_and_clear()

if __name__ == "__main__":
    app = ADBLoggerApp()
    app.mainloop()