"""
OpenFlow Windows Single-Instance Guard
Ensures only one instance of OpenFlow runs per user session.
If another instance is launched:
- Signals the existing instance to bring its window to foreground.
- Exits the secondary process immediately before initializing audio or speech models.
"""
import ctypes
from ctypes import wintypes
from utils_logger import log_info, log_warning

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\OpenFlow_SingleInstance_Mutex_v110"
WINDOW_TITLE = "OpenFlow"


class SingleInstanceGuard:
    def __init__(self):
        self.mutex_handle = None
        self.is_primary = False

    def acquire(self) -> bool:
        """
        Attempts to acquire the named mutex.
        Returns True if this is the only running instance.
        Returns False if another instance already exists.
        """
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        
        self.mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        last_error = kernel32.GetLastError()

        if last_error == ERROR_ALREADY_EXISTS:
            log_warning("[SingleInstance] Another instance of OpenFlow is already running.")
            self._activate_existing_window()
            return False

        self.is_primary = True
        log_info(f"[SingleInstance] Primary instance lock acquired (mutex_handle={self.mutex_handle}).")
        return True

    def _activate_existing_window(self):
        """Attempts to find and activate the window of the running instance."""
        try:
            hwnd = user32.FindWindowW(None, WINDOW_TITLE)
            if hwnd:
                log_info(f"[SingleInstance] Activating existing OpenFlow window (HWND={hwnd})...")
                # If minimized, restore it
                user32.ShowWindow(hwnd, 9) # SW_RESTORE = 9
                user32.SetForegroundWindow(hwnd)
        except Exception as e:
            log_warning(f"[SingleInstance] Could not bring existing window to foreground: {e}")

    def release(self):
        """Releases the mutex handle upon application exit."""
        if self.mutex_handle:
            kernel32.CloseHandle(self.mutex_handle)
            self.mutex_handle = None
            log_info("[SingleInstance] Primary instance mutex released.")
