"""
OpenFlow global hotkey manager (Ctrl+Shift+Space).

Architecture:
- Native Win32 WH_KEYBOARD_LL hook on a dedicated thread with its own Win32 message loop.
- Fallback GetAsyncKeyState poller that ONLY activates if the native hook fails or stops receiving events.
- Single atomic latch and debounce mechanism shared across any event trigger.
- Explicit unlatching on Space key release.
- Strict single-callback dispatch: exactly one toggle per physical press of Ctrl+Shift+Space.
- Logs key codes ONLY for Ctrl, Shift, and Space. Never logs any other user keystrokes.
"""
import time
import threading
import ctypes
from ctypes import wintypes
from typing import Callable, Optional
from utils_logger import log_info, log_warning, log_error

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
VK_SHIFT, VK_CONTROL, VK_SPACE = 0x10, 0x11, 0x20
CTRL_VKS = (0xA2, 0xA3, VK_CONTROL) # LCTRL, RCTRL, CONTROL
SHIFT_VKS = (0xA0, 0xA1, VK_SHIFT)  # LSHIFT, RSHIFT, SHIFT

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

# 64-bit argument signatures
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('vkCode', wintypes.DWORD),
        ('scanCode', wintypes.DWORD),
        ('flags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t)
    ]


class GlobalHotkeyManager:
    def __init__(self, callback: Callable[[], None], debounce_seconds: float = 0.45):
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.is_running = False
        self.hook_handle = None
        self.hook_error = 0
        self.hook_thread: Optional[threading.Thread] = None
        self.poller_thread: Optional[threading.Thread] = None
        self.hook_thread_id = None
        self.loop_running = False
        self.hook_events_seen = 0
        self.last_hook_event = 0.0
        self.trigger_count = 0
        
        self._ctrl_down = False
        self._shift_down = False
        self._latched = False          # True from trigger until Space/Ctrl/Shift is released
        self._last_trigger = 0.0
        self._lock = threading.Lock()
        self._c_proc = None

    @property
    def is_registered(self) -> bool:
        """Real health: hook installed AND its thread + message loop are alive."""
        return bool(self.is_running and self.hook_handle and self.loop_running
                    and self.hook_thread is not None and self.hook_thread.is_alive())

    def health(self) -> dict:
        return {
            "hook_installed": bool(self.hook_handle),
            "hook_error": self.hook_error,
            "hook_thread_alive": bool(self.hook_thread and self.hook_thread.is_alive()),
            "message_loop": self.loop_running,
            "hook_events_seen": self.hook_events_seen,
            "poller_alive": bool(self.poller_thread and self.poller_thread.is_alive()),
            "triggers": self.trigger_count,
        }

    def _fire(self, source: str):
        with self._lock:
            now = time.time()
            if self._latched:
                log_info(f"[Hotkey] {source}: ignored (chord held / latched)")
                return
            if now - self._last_trigger < self.debounce_seconds:
                log_info(f"[Hotkey] {source}: ignored by debounce ({now - self._last_trigger:.3f}s < {self.debounce_seconds}s)")
                return
            self._latched = True
            self._last_trigger = now
            self.trigger_count += 1
            trigger_id = self.trigger_count

        log_info(f"[Hotkey] {source}: Ctrl+Shift+Space detected -> invoking callback (#{trigger_id})")
        threading.Thread(target=self._run_callback, name="HotkeyCallback", daemon=True).start()

    def _run_callback(self):
        try:
            self.callback()
            log_info("[Hotkey] Dictation callback returned OK")
        except Exception as e:
            log_error("[Hotkey] Dictation callback raised exception", e)

    def _hook_proc(self, nCode, wParam, lParam):
        try:
            if nCode >= 0:
                vk = KBDLLHOOKSTRUCT.from_address(lParam).vkCode
                down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                up = wParam in (WM_KEYUP, WM_SYSKEYUP)

                if vk in CTRL_VKS or vk in SHIFT_VKS or vk == VK_SPACE:
                    self.hook_events_seen += 1
                    self.last_hook_event = time.time()
                    log_info(f"[Hotkey] Hook key vk=0x{vk:02X} ({'down' if down else 'up'})")

                if vk in CTRL_VKS:
                    self._ctrl_down = down
                    if up and not self._ctrl_down:
                        with self._lock:
                            self._latched = False
                elif vk in SHIFT_VKS:
                    self._shift_down = down
                    if up and not self._shift_down:
                        with self._lock:
                            self._latched = False
                elif vk == VK_SPACE:
                    if down:
                        # Double-check async states to avoid missing modifier presses
                        c_async = bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                        s_async = bool(user32.GetAsyncKeyState(VK_SHIFT) & 0x8000)
                        if (self._ctrl_down or c_async) and (self._shift_down or s_async):
                            self._fire("hook")
                    elif up:
                        with self._lock:
                            self._latched = False

        except Exception as e:
            log_error("[Hotkey] Exception in low-level hook procedure", e)

        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _message_loop(self):
        self.hook_thread_id = kernel32.GetCurrentThreadId()
        log_info(f"[Hotkey] Native hook thread started (tid={self.hook_thread_id})")
        self._c_proc = HOOKPROC(self._hook_proc)
        self.hook_handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._c_proc, None, 0)
        self.hook_error = ctypes.get_last_error() or kernel32.GetLastError()
        
        if not self.hook_handle:
            log_error(f"[Hotkey] SetWindowsHookExW failed: GetLastError={self.hook_error}")
            return
            
        log_info(f"[Hotkey] Native hook installed: handle={self.hook_handle}, GetLastError={self.hook_error}")
        msg = wintypes.MSG()
        self.loop_running = True
        try:
            while self.is_running:
                r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if r <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as e:
            log_error("[Hotkey] Message loop encountered exception", e)
        finally:
            self.loop_running = False
            if self.hook_handle:
                user32.UnhookWindowsHookEx(self.hook_handle)
                log_info(f"[Hotkey] Native hook unhooked (handle={self.hook_handle})")
                self.hook_handle = None

    def _poll_loop(self):
        """
        Backup poller that only intervenes if the native hook has failed to install
        or has stopped receiving any keyboard events for over 3 seconds.
        """
        log_info("[Hotkey] Poller thread started (inactive while native hook is healthy)")
        prev_chord = False
        while self.is_running:
            try:
                # If hook is installed, healthy, and receiving events, let the hook handle it
                hook_healthy = (self.hook_handle and self.loop_running and (time.time() - self.last_hook_event < 3.0 or self.hook_events_seen > 0))
                
                # Check hardware state
                c = bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                s = bool(user32.GetAsyncKeyState(VK_SHIFT) & 0x8000)
                sp = bool(user32.GetAsyncKeyState(VK_SPACE) & 0x8000)

                if not sp or not (c and s):
                    with self._lock:
                        if not sp:
                            self._latched = False

                chord = c and s and sp
                if chord and not prev_chord:
                    if not hook_healthy:
                        log_info("[Hotkey] Native hook not receiving events; triggering via backup poller")
                        self._fire("poller")
                prev_chord = chord
            except Exception as e:
                log_error("[Hotkey] Poller encountered error", e)
            time.sleep(0.04) # 25 Hz check
        log_info("[Hotkey] Poller thread exiting")

    def start(self) -> bool:
        if self.is_running:
            return self.is_registered
        self.is_running = True
        log_info("[Hotkey] Manager starting...")
        self.hook_thread = threading.Thread(target=self._message_loop, name="HotkeyHook", daemon=True)
        self.hook_thread.start()
        self.poller_thread = threading.Thread(target=self._poll_loop, name="HotkeyPoller", daemon=True)
        self.poller_thread.start()
        
        for _ in range(40):
            if self.loop_running or (self.hook_thread and not self.hook_thread.is_alive()):
                break
            time.sleep(0.05)
            
        log_info(f"[Hotkey] Start completed: registered={self.is_registered}, health={self.health()}")
        return self.is_registered

    def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        if self.hook_thread_id:
            user32.PostThreadMessageW(self.hook_thread_id, 0x0012, 0, 0) # WM_QUIT
        for t in (self.hook_thread, self.poller_thread):
            if t and t.is_alive():
                t.join(timeout=1.0)
        log_info("[Hotkey] Manager stopped.")
