import time
import ctypes
import pyperclip

# Virtual-Key codes for Windows
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_SPACE = 0x20
VK_V = 0x56

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', ctypes.c_ushort),
        ('wScan', ctypes.c_ushort),
        ('dwFlags', ctypes.c_ulong),
        ('time', ctypes.c_ulong),
        ('dwExtraInfo', ctypes.c_void_p)
    ]

class INPUT(ctypes.Structure):
    class _INPUT_UNION(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT)]
    _anonymous_ = ('_u',)
    _fields_ = [
        ('type', ctypes.c_ulong),
        ('_u', _INPUT_UNION)
    ]

def _wait_for_modifier_keys_release(timeout: float = 0.5):
    """
    Waits for modifier keys (Ctrl, Shift, Alt, Space) to be physically released.
    Prevents synthetic Ctrl+V from becoming Ctrl+Shift+V or colliding with user hotkey release.
    """
    keys = (VK_CONTROL, VK_SHIFT, VK_MENU, VK_SPACE)
    start = time.perf_counter()
    while time.perf_counter() - start < timeout:
        if not any(bool(user32.GetAsyncKeyState(k) & 0x8000) for k in keys):
            return
        time.sleep(0.01)

def _send_ctrl_v():
    """
    Simulates Ctrl+V using hardware-level SendInput API with modifier safety.
    Guarantees reliable delivery across browsers, Electron apps, and standard native controls.
    """
    inputs = (INPUT * 4)()

    # 1. Ctrl down
    inputs[0].type = INPUT_KEYBOARD
    inputs[0].ki.wVk = VK_CONTROL
    inputs[0].ki.dwFlags = 0

    # 2. V down
    inputs[1].type = INPUT_KEYBOARD
    inputs[1].ki.wVk = VK_V
    inputs[1].ki.dwFlags = 0

    # 3. V up
    inputs[2].type = INPUT_KEYBOARD
    inputs[2].ki.wVk = VK_V
    inputs[2].ki.dwFlags = KEYEVENTF_KEYUP

    # 4. Ctrl up
    inputs[3].type = INPUT_KEYBOARD
    inputs[3].ki.wVk = VK_CONTROL
    inputs[3].ki.dwFlags = KEYEVENTF_KEYUP

    # Ensure any held Shift/Alt are released virtually if stuck
    user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

    cb_sent = user32.SendInput(4, ctypes.byref(inputs), ctypes.sizeof(INPUT))
    if cb_sent != 4:
        # Fallback to keybd_event if SendInput failed
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.01)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

def _safe_paste(retries: int = 5, delay: float = 0.02):
    """Safely retrieves current clipboard text, retrying if locked by another app."""
    for attempt in range(retries):
        try:
            return pyperclip.paste()
        except Exception:
            if attempt < retries - 1:
                time.sleep(delay)
    return None

def _safe_copy(text: str, retries: int = 5, delay: float = 0.02) -> bool:
    """Safely copies text to the clipboard, retrying if locked."""
    for attempt in range(retries):
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            if attempt < retries - 1:
                time.sleep(delay)
    return False

def restore_target_window(target_hwnd: int) -> bool:
    """
    Robustly restores focus to the original target application window.
    Uses Win32 AttachThreadInput and SetForegroundWindow to bypass Windows focus restrictions.
    """
    if not target_hwnd or not user32.IsWindow(target_hwnd):
        return False
    current_fg = user32.GetForegroundWindow()
    if current_fg == target_hwnd:
        return True

    fg_thread = user32.GetWindowThreadProcessId(current_fg, None)
    cur_thread = kernel32.GetCurrentThreadId()

    attached = False
    if fg_thread and fg_thread != cur_thread:
        attached = bool(user32.AttachThreadInput(cur_thread, fg_thread, True))

    try:
        user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(target_hwnd)
        user32.BringWindowToTop(target_hwnd)
        user32.SetFocus(target_hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur_thread, fg_thread, False)

    time.sleep(0.05)
    return user32.GetForegroundWindow() == target_hwnd

def insert_text(text: str, paste_wait: float = 0.20, target_hwnd: int = 0) -> bool:
    """
    Pastes text into the currently active focused window using the clipboard,
    preserving preexisting clipboard contents (including Unicode & multiline).
    
    Args:
        text: The dictated text snippet to inject.
        paste_wait: Duration in seconds to allow destination window message loop
                    to consume synthesized Ctrl+V message before restoring clipboard.
        target_hwnd: Optional target window HWND to restore focus to before pasting.
    """
    if not text:
        return False

    t_start = time.perf_counter()
    text_len = len(text)
    print(f"[{time.strftime('%H:%M:%S')}] [engine_injector] Initiating injection (length: {text_len} chars, target_hwnd: {target_hwnd})")

    # 1. Wait for user to release hotkey modifiers (e.g. Ctrl+Shift+Space)
    _wait_for_modifier_keys_release(timeout=0.3)

    # 2. Restore focus to the target application if needed
    if target_hwnd:
        restored = restore_target_window(target_hwnd)
        if not restored:
            print(f"[{time.strftime('%H:%M:%S')}] [engine_injector] Warning: Target HWND {target_hwnd} could not be brought to foreground (current: {user32.GetForegroundWindow()})")

    # 3. Save original clipboard contents before any modification
    old_clipboard = _safe_paste()

    try:
        # 4. Place dictated text onto clipboard
        copied = _safe_copy(text)
        if not copied:
            print(f"[{time.strftime('%H:%M:%S')}] [engine_injector] Injection failed: Failed to copy text to clipboard (length: {text_len})")
            return False

        # Give OS message queue a moment to finalize clipboard update
        time.sleep(0.03)

        # 5. Synthesize Ctrl+V to active destination window
        _send_ctrl_v()

        # 6. Critical synchronization window:
        # Allow the destination application message loop to receive WM_KEYDOWN,
        # handle WM_PASTE / GetClipboardData, and process before restoration.
        time.sleep(paste_wait)
        elapsed = time.perf_counter() - t_start
        print(f"[{time.strftime('%H:%M:%S')}] [engine_injector] Injection succeeded (length: {text_len} chars, duration: {elapsed:.3f}s)")
        return True
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] [engine_injector] Injection failed: Error during text injection (length: {text_len}): {e}")
        return False
    finally:
        # 7. Restore original clipboard content reliably
        if old_clipboard is not None:
            _safe_copy(old_clipboard)
