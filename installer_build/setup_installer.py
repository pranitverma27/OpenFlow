"""
OpenFlow Self-Contained Standalone Windows Setup Wizard
- Embedded zip payload extracted at runtime into %LOCALAPPDATA%\\Programs\\OpenFlow
- True standalone single-executable installer (.exe)
- No separate ZIP download required by end-user
- Desktop & Start Menu shortcuts
- Uninstaller registration
- Preserves %APPDATA%\\OpenFlow (user settings & corrections)
"""
import os
import sys
import shutil
import subprocess
import zipfile
import json
import tkinter as tk
from tkinter import messagebox, ttk

APP_NAME = "OpenFlow"
APP_VERSION = "1.1.0"
DEFAULT_INSTALL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", APP_NAME)

def get_bundle_dir():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    elif getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_user_data_dir():
    appdata = os.environ.get("APPDATA")
    candidates = []
    if appdata:
        candidates.append(os.path.join(appdata, APP_NAME))
    candidates.append(os.path.join(os.path.expanduser("~"), ".openflow"))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "user_data"))

    for candidate in candidates:
        try:
            os.makedirs(candidate, exist_ok=True)
            test_file = os.path.join(candidate, ".write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            return candidate
        except (PermissionError, OSError):
            continue
    fallback = os.path.join(os.path.expanduser("~"), APP_NAME)
    os.makedirs(fallback, exist_ok=True)
    return fallback

def create_windows_shortcut(target_path, shortcut_path, description="", icon_path=""):
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = target_path
        shortcut.WorkingDirectory = os.path.dirname(target_path)
        shortcut.Description = description
        if icon_path and os.path.exists(icon_path):
            shortcut.IconLocation = icon_path
        shortcut.Save()
        return True
    except Exception:
        ps_cmd = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$s = $ws.CreateShortcut("{shortcut_path}"); '
            f'$s.TargetPath = "{target_path}"; '
            f'$s.WorkingDirectory = "{os.path.dirname(target_path)}"; '
            f'$s.Description = "{description}"; '
            f'$s.Save()'
        )
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True)
            return os.path.exists(shortcut_path)
        except Exception:
            return False

def register_uninstall(install_dir):
    """
    Per-user (HKCU, no administrator privileges required) registration
    so OpenFlow appears in Windows Settings > Apps > Installed apps.
    """
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenFlow"
    exe = os.path.join(install_dir, "OpenFlow.exe")
    unin = os.path.join(install_dir, "Uninstall.cmd")

    size_kb = 0
    try:
        for r, d, fs in os.walk(install_dir):
            for f in fs:
                try:
                    size_kb += os.path.getsize(os.path.join(r, f)) // 1024
                except OSError:
                    pass
    except Exception:
        size_kb = 150000

    values = [
        ("DisplayName", "OpenFlow", winreg.REG_SZ),
        ("DisplayVersion", APP_VERSION, winreg.REG_SZ),
        ("Publisher", "Pranit Verma", winreg.REG_SZ),
        ("InstallLocation", install_dir, winreg.REG_SZ),
        ("DisplayIcon", f'"{exe}",0', winreg.REG_SZ),
        ("UninstallString", f'cmd.exe /c "{unin}"', winreg.REG_SZ),
        ("QuietUninstallString", f'cmd.exe /c "{unin}" /quiet', winreg.REG_SZ),
        ("EstimatedSize", int(size_kb), winreg.REG_DWORD),
        ("NoModify", 1, winreg.REG_DWORD),
        ("NoRepair", 1, winreg.REG_DWORD),
    ]

    # Desired access: write permission (creates subkeys & sets values) in 64-bit view
    access_flags = winreg.KEY_WRITE
    if hasattr(winreg, "KEY_WOW64_64KEY"):
        access_flags |= winreg.KEY_WOW64_64KEY

    primary_error = None
    try:
        parent_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, parent_path, 0, access_flags) as parent_key:
            with winreg.CreateKeyEx(parent_key, "OpenFlow", 0, access_flags) as k:
                for name, val, vtype in values:
                    winreg.SetValueEx(k, name, 0, vtype, val)
        return True
    except Exception as e:
        primary_error = e

    # Secondary fallback: Use Windows built-in reg.exe command
    try:
        hkcu_target = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenFlow"
        for name, val, vtype in values:
            type_str = "REG_DWORD" if vtype == winreg.REG_DWORD else "REG_SZ"
            cmd = ["reg", "add", hkcu_target, "/v", name, "/t", type_str, "/d", str(val), "/f"]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            if res.returncode != 0:
                raise RuntimeError(f"reg.exe failed for '{name}': {res.stderr.strip() or res.stdout.strip()}")
        return True
    except Exception as fallback_error:
        err_msg = (
            f"Failed to register OpenFlow in Windows registry at "
            f"HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\OpenFlow.\n"
            f"Primary WinReg error: {primary_error}\n"
            f"Fallback reg.exe error: {fallback_error}"
        )
        raise PermissionError(err_msg) from primary_error


def generate_uninstaller(install_dir):
    uninstaller_path = os.path.join(install_dir, "Uninstall.cmd")
    script = (
        "@echo off\r\n"
        "title Uninstalling OpenFlow\r\n"
        "echo Closing running OpenFlow instances...\r\n"
        "taskkill /f /im OpenFlow.exe >nul 2>&1\r\n"
        "del /q \"%USERPROFILE%\\Desktop\\OpenFlow.lnk\" >nul 2>&1\r\n"
        "del /q \"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\OpenFlow.lnk\" >nul 2>&1\r\n"
        "reg delete \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\OpenFlow\" /f /reg:64 >nul 2>&1\r\n"
        "reg delete \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\OpenFlow\" /f >nul 2>&1\r\n"
        "echo Your settings and dictionary in %APPDATA%\\OpenFlow are preserved.\r\n"
        "cd /d \"%TEMP%\"\r\n"
        f"start \"\" /b cmd /c \"ping 127.0.0.1 -n 3 >nul & rd /s /q \"{install_dir}\"\"\r\n"
        "echo OpenFlow has been removed.\r\n"
        "if /i not \"%~1\"==\"/quiet\" pause\r\n"
    )
    with open(uninstaller_path, "w", encoding="utf-8") as f:
        f.write(script)
    return uninstaller_path


def perform_install(target_dir, create_desktop=True, create_start_menu=True, progress_cb=None):
    bundle_dir = get_bundle_dir()
    embedded_payload = os.path.join(bundle_dir, "payload.zip")

    # If payload.zip is present, extract from embedded zip
    if os.path.exists(embedded_payload):
        os.makedirs(target_dir, exist_ok=True)
        with zipfile.ZipFile(embedded_payload, "r") as zf:
            infolist = zf.infolist()
            total_items = len(infolist)
            for idx, item in enumerate(infolist):
                zf.extract(item, target_dir)
                if progress_cb and total_items > 0:
                    progress_cb(int((idx / total_items) * 75))
    else:
        # Fallback to loose dist directory if running from development source
        dev_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "release_v2", "dist", "OpenFlow")
        if not os.path.exists(dev_src):
            dev_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dist", "OpenFlow")
        if not os.path.exists(dev_src):
            raise FileNotFoundError(f"Neither embedded payload.zip nor loose distribution found at: {dev_src}")
        total_files = sum([len(files) for r, d, files in os.walk(dev_src)])
        copied = 0
        for root, dirs, files in os.walk(dev_src):
            rel = os.path.relpath(root, dev_src)
            dest_dir = os.path.join(target_dir, rel) if rel != "." else target_dir
            os.makedirs(dest_dir, exist_ok=True)
            for f in files:
                sf = os.path.join(root, f)
                df = os.path.join(dest_dir, f)
                shutil.copy2(sf, df)
                copied += 1
                if progress_cb and total_files > 0:
                    progress_cb(int((copied / total_files) * 75))

    if progress_cb:
        progress_cb(80)

    exe_path = os.path.join(target_dir, "OpenFlow.exe")
    if not os.path.exists(exe_path):
        raise FileNotFoundError(f"Installation failed: OpenFlow.exe missing in destination directory: {target_dir}")

    generate_uninstaller(target_dir)

    if progress_cb:
        progress_cb(85)

    # Registration failure must be visible, descriptive, not silent
    register_uninstall(target_dir)

    if progress_cb:
        progress_cb(90)

    if create_desktop:
        try:
            desktop = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
            if os.path.exists(desktop):
                create_windows_shortcut(exe_path, os.path.join(desktop, "OpenFlow.lnk"), "OpenFlow Offline Dictation")
        except Exception as e:
            print(f"[Setup] Notice creating desktop shortcut: {e}")

    if create_start_menu:
        try:
            start_menu = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
            if os.path.exists(start_menu):
                create_windows_shortcut(exe_path, os.path.join(start_menu, "OpenFlow.lnk"), "OpenFlow Offline Dictation")
        except Exception as e:
            print(f"[Setup] Notice creating start menu shortcut: {e}")

    try:
        user_dir = get_user_data_dir()
        dict_file = os.path.join(user_dir, "corrections.json")
        if not os.path.exists(dict_file):
            with open(dict_file, "w", encoding="utf-8") as f:
                json.dump({"description": "OpenFlow personal corrections dictionary"}, f, indent=2)
    except Exception as e:
        print(f"[Setup] Notice initializing user dictionary: {e}")

    if progress_cb:
        progress_cb(100)

class InstallerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"OpenFlow v{APP_VERSION} Setup")
        self.root.geometry("520x370")
        self.root.resizable(False, False)

        bg_color = "#1e1e2e"
        fg_color = "#cdd6f4"
        accent_color = "#89b4fa"
        self.root.configure(bg=bg_color)

        title_lbl = tk.Label(self.root, text="Install OpenFlow", font=("Segoe UI", 16, "bold"), bg=bg_color, fg=accent_color)
        title_lbl.pack(pady=(20, 5))

        subtitle = tk.Label(self.root, text="Privacy-first, offline dictation for Windows", font=("Segoe UI", 10), bg=bg_color, fg="#a6adc8")
        subtitle.pack(pady=(0, 20))

        frm = tk.Frame(self.root, bg=bg_color)
        frm.pack(fill="x", padx=30, pady=10)

        lbl_dir = tk.Label(frm, text="Destination Folder:", font=("Segoe UI", 9, "bold"), bg=bg_color, fg=fg_color)
        lbl_dir.pack(anchor="w")

        self.dir_var = tk.StringVar(value=DEFAULT_INSTALL_DIR)
        entry_dir = tk.Entry(frm, textvariable=self.dir_var, font=("Segoe UI", 9), width=50)
        entry_dir.pack(fill="x", pady=(5, 15))

        self.cb_desktop_var = tk.BooleanVar(value=True)
        cb_desktop = tk.Checkbutton(frm, text="Create a Desktop shortcut", variable=self.cb_desktop_var, bg=bg_color, fg=fg_color, selectcolor=bg_color, activebackground=bg_color)
        cb_desktop.pack(anchor="w")

        self.cb_start_var = tk.BooleanVar(value=True)
        cb_start = tk.Checkbutton(frm, text="Create a Start Menu shortcut", variable=self.cb_start_var, bg=bg_color, fg=fg_color, selectcolor=bg_color, activebackground=bg_color)
        cb_start.pack(anchor="w")

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=460, mode="determinate")
        self.progress.pack(pady=(15, 10))

        self.status_lbl = tk.Label(self.root, text="Ready to install.", font=("Segoe UI", 9), bg=bg_color, fg="#a6adc8")
        self.status_lbl.pack()

        btn_frm = tk.Frame(self.root, bg=bg_color)
        btn_frm.pack(side="bottom", pady=20)

        self.btn_install = tk.Button(btn_frm, text="Install", font=("Segoe UI", 10, "bold"), bg=accent_color, fg="#11111b", width=12, command=self.start_install)
        self.btn_install.pack(side="left", padx=10)

        self.btn_cancel = tk.Button(btn_frm, text="Cancel", font=("Segoe UI", 10), bg="#45475a", fg=fg_color, width=12, command=self.root.destroy)
        self.btn_cancel.pack(side="left", padx=10)

    def start_install(self):
        self.btn_install.config(state="disabled")
        self.status_lbl.config(text="Extracting and installing OpenFlow files...")
        self.root.update()

        def update_progress(val):
            self.progress["value"] = val
            self.root.update()

        try:
            target = self.dir_var.get().strip()
            if not target:
                target = DEFAULT_INSTALL_DIR
            perform_install(
                target_dir=target,
                create_desktop=self.cb_desktop_var.get(),
                create_start_menu=self.cb_start_var.get(),
                progress_cb=update_progress
            )
            self.status_lbl.config(text="Installation Complete!", fg="#a6e3a1")
            messagebox.showinfo(
                "Installation Complete",
                f"OpenFlow has been successfully installed to:\n{target}\n\n"
                "You can launch it anytime with global hotkey Ctrl+Shift+Space."
            )
            self.root.destroy()
        except Exception as e:
            self.btn_install.config(state="normal")
            self.btn_cancel.config(state="normal")
            self.status_lbl.config(text="Installation failed. Ready to retry.", fg="#f38ba8")
            self.progress["value"] = 0
            messagebox.showerror(
                "Installation Error",
                f"Failed to install OpenFlow:\n\n{str(e)}\n\n"
                "You may select a different destination folder and click Install to retry."
            )

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    if "--silent" in sys.argv:
        print(f"Silent installing to {DEFAULT_INSTALL_DIR}...")
        try:
            perform_install(DEFAULT_INSTALL_DIR, True, True)
            print("Installation complete.")
            sys.exit(0)
        except Exception as e:
            print(f"Installation failed: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            app = InstallerGUI()
            app.run()
        except Exception as e:
            print(f"GUI launch failed ({e}), attempting console installation...")
            try:
                perform_install(DEFAULT_INSTALL_DIR, True, True)
                print("Installation complete.")
                sys.exit(0)
            except Exception as install_err:
                print(f"Installation failed: {install_err}", file=sys.stderr)
                sys.exit(1)
