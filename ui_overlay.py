"""
OpenFlow System-Wide Floating Status Overlay
Compact, non-activating, always-on-top indicator pill showing real-time dictation state:
- "Listening":
  - Pale translucent pink/red background (#FFF0F0) with vibrant red border (#EF4444)
  - Red circular status dot
  - Dark high-contrast "Listening" typography
  - Red audio waveform bars tightly positioned on right, reacting dynamically to mic volume
- "Transcribing":
  - Pale cream/yellow background (#FEF9EE) with amber border (#F59E0B)
  - Amber circular status dot
  - Dark high-contrast "Transcribing" typography
  - Circular amber spinner smoothly animated on right
- "Text inserted":
  - Pale emerald background (#ECFDF5) with green border (#10B981)
  - Green circular status dot with "Text inserted" and checkmark (auto-hides after 1.5s)
- "Error":
  - Red alert indicator (auto-hides after 2.5s)

Pure Win32 implementation (ctypes only, zero pythonnet/WinForms dependency).
Never steals focus from active applications or browser text fields (SW_SHOWNOACTIVATE / WS_EX_NOACTIVATE / SetWindowPos).
Supports multi-monitor setups (positions centered at the top of the active target window's monitor).
"""
import ctypes
from ctypes import wintypes
import threading
import time
import math

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# Win32 Constants
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
CS_DROPSHADOW = 0x00020000

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

WM_DESTROY = 0x0002
WM_PAINT = 0x000F
WM_USER = 0x0400
WM_UPDATE_STATUS = WM_USER + 1
WM_HIDE_STATUS = WM_USER + 2
WM_REPOSITION = WM_USER + 3
WM_ANIM_TICK = WM_USER + 4

DT_LEFT = 0x00000000
DT_CENTER = 0x00000001
DT_VCENTER = 0x00000004
DT_SINGLELINE = 0x00000020
DT_NOPREFIX = 0x00000800

MONITOR_DEFAULTTONEAREST = 2

class RECT(ctypes.Structure):
    _fields_ = [
        ('left', wintypes.LONG),
        ('top', wintypes.LONG),
        ('right', wintypes.LONG),
        ('bottom', wintypes.LONG)
    ]

class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('rcMonitor', RECT),
        ('rcWork', RECT),
        ('dwFlags', wintypes.DWORD)
    ]

class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ('hdc', wintypes.HDC),
        ('fErase', wintypes.BOOL),
        ('rcPaint', RECT),
        ('fRestore', wintypes.BOOL),
        ('fIncUpdate', wintypes.BOOL),
        ('rgbReserved', wintypes.BYTE * 32)
    ]

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.UINT),
        ('style', wintypes.UINT),
        ('lpfnWndProc', ctypes.c_void_p),
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', wintypes.HINSTANCE),
        ('hIcon', wintypes.HICON),
        ('hCursor', wintypes.HICON),
        ('hbrBackground', wintypes.HBRUSH),
        ('lpszMenuName', wintypes.LPCWSTR),
        ('lpszClassName', wintypes.LPCWSTR),
        ('hIconSm', wintypes.HICON)
    ]

# Setup explicit ctypes 64-bit signatures
WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_longlong

user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
]

user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.UINT
]

user32.SetWindowRgn.restype = ctypes.c_int
user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]

user32.MonitorFromWindow.restype = ctypes.c_void_p
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]

user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]

gdi32.CreateRoundRectRgn.restype = wintypes.HRGN
gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]

gdi32.RoundRect.restype = wintypes.BOOL
gdi32.RoundRect.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]

gdi32.CreatePen.restype = wintypes.HPEN
gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.COLORREF]

gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]

gdi32.CreateFontW.restype = wintypes.HFONT

gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]

gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]

gdi32.MoveToEx.restype = wintypes.BOOL
gdi32.MoveToEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_void_p]

gdi32.LineTo.restype = wintypes.BOOL
gdi32.LineTo.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]

gdi32.Arc.restype = wintypes.BOOL
gdi32.Arc.argtypes = [
    wintypes.HDC,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int
]


class FloatingOverlay:
    """
    Lightweight, pure Win32 floating status pill.
    Features:
    - Compact horizontal capsule (220-250px wide x 48px tall)
    - Pale pink fill + bright red border for Listening
    - Pale cream fill + vibrant amber border for Transcribing
    - Active monitor targeting via MonitorFromWindow/GetMonitorInfoW
    - Reactive audio waveform responding dynamically to mic input level (RMS + attack/release)
    - Smooth rotating circular amber spinner during transcription
    - Topmost, non-activating, zero focus-stealing.
    """
    def _ensure_dpi_awareness(self):
        """Enable Per-Monitor DPI awareness for accurate multi-monitor geometry."""
        try:
            shcore = ctypes.windll.shcore
            # PROCESS_PER_MONITOR_DPI_AWARE = 2
            shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass

    def __init__(self):
        self._ensure_dpi_awareness()
        self._hwnd = None
        self._state_label = "Listening"
        self._dot_color_bgr = 0x002828DC    # Red dot (RGB: 220, 40, 40)
        self._border_color_bgr = 0x003333EF # Bright red border (RGB: 239, 51, 51)
        self._bg_color_bgr = 0x00F5F2FE     # Pale pink fill (RGB: 254, 242, 245)
        self._right_mode = "wave"           # "wave" | "spinner" | "check" | "error"
        self._accent_color_bgr = 0x002828DC # Red accent
        self._bg_brush = None
        self._border_pen = None
        self._font_label = None
        self._font_icon = None
        self._thread = None
        self._hide_timer = None
        self._lock = threading.Lock()
        self._ready_event = threading.Event()
        self._wndproc_ref = None

        # Audio visualization & animation state
        self._target_level = 0.0
        self._smoothed_level = 0.0
        self._spinner_angle = 0.0
        self._anim_running = False
        self._anim_thread = None

        # Compact capsule dimensions (scaled tightly to content)
        self._pill_width = 236
        self._pill_height = 48
        self._target_x = 0
        self._target_y = 75

        self._thread = threading.Thread(target=self._run_msg_loop, daemon=True)
        self._thread.start()
        # Wait up to 1.0s for HWND creation so immediate show calls never drop
        self._ready_event.wait(timeout=1.0)

    def _calculate_monitor_pos(self, target_hwnd: int = 0):
        """Calculates horizontal center and top-75 offset on the target window's monitor."""
        width = self._pill_width
        height = self._pill_height
        offset_y = 75

        if target_hwnd and user32.IsWindow(target_hwnd):
            hmon = user32.MonitorFromWindow(target_hwnd, MONITOR_DEFAULTTONEAREST)
        else:
            fg = user32.GetForegroundWindow()
            hmon = user32.MonitorFromWindow(fg, MONITOR_DEFAULTTONEAREST) if fg else None

        if hmon:
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                mon_left = mi.rcMonitor.left
                mon_top = mi.rcMonitor.top
                mon_width = mi.rcMonitor.right - mi.rcMonitor.left
                x = mon_left + (mon_width - width) // 2
                y = mon_top + offset_y
                return x, y

        # Fallback to primary screen metrics
        sw = user32.GetSystemMetrics(0)
        x = (sw - width) // 2
        y = offset_y
        return x, y

    def _run_msg_loop(self):
        hinst = kernel32.GetModuleHandleW(None)
        class_name = f"OpenFlowOverlayClass_{id(self)}"

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_PAINT:
                ps = PAINTSTRUCT()
                hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
                rect = RECT()
                user32.GetClientRect(hwnd, ctypes.byref(rect))
                width = rect.right - rect.left
                height = rect.bottom - rect.top

                # Double buffering to prevent any flicker
                mem_dc = gdi32.CreateCompatibleDC(hdc)
                mem_bm = gdi32.CreateCompatibleBitmap(hdc, width, height)
                old_bm = gdi32.SelectObject(mem_dc, mem_bm)

                # Fill with state-dependent pale translucent-tone background
                bg_brush = gdi32.CreateSolidBrush(self._bg_color_bgr)
                # Crisp 2px border matching state color
                border_pen = gdi32.CreatePen(0, 2, self._border_color_bgr)

                old_pen = gdi32.SelectObject(mem_dc, border_pen)
                old_brush = gdi32.SelectObject(mem_dc, bg_brush)

                # Draw smooth rounded capsule background (24px radius = fully rounded for height 48)
                gdi32.RoundRect(mem_dc, 0, 0, width, height, 24, 24)

                gdi32.SetBkMode(mem_dc, 1) # TRANSPARENT

                # 1. Left circular status dot (diameter 8px, centered at y = height // 2)
                dot_size = 8
                dot_x = 18
                dot_y = (height - dot_size) // 2
                dot_brush = gdi32.CreateSolidBrush(self._dot_color_bgr)
                dot_pen = gdi32.CreatePen(0, 1, self._dot_color_bgr)
                prev_b = gdi32.SelectObject(mem_dc, dot_brush)
                prev_p = gdi32.SelectObject(mem_dc, dot_pen)
                gdi32.RoundRect(mem_dc, dot_x, dot_y, dot_x + dot_size, dot_y + dot_size, dot_size, dot_size)
                gdi32.SelectObject(mem_dc, prev_p)
                gdi32.SelectObject(mem_dc, prev_b)
                gdi32.DeleteObject(dot_brush)
                gdi32.DeleteObject(dot_pen)

                # 2. Status label ("Listening" / "Transcribing" / "Text inserted")
                if not self._font_label:
                    self._font_label = gdi32.CreateFontW(
                        16, 0, 0, 0, 600, False, False, False,
                        1, 0, 0, 5, 0, "Segoe UI"
                    )
                old_font = gdi32.SelectObject(mem_dc, self._font_label)
                gdi32.SetTextColor(mem_dc, 0x000F172A) # Dark high-contrast slate #0F172A
                label_x = dot_x + dot_size + 10
                label_rect = RECT(label_x, 0, width - 60, height)
                user32.DrawTextW(
                    mem_dc, self._state_label, -1, ctypes.byref(label_rect),
                    DT_LEFT | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX
                )

                # 3. Right indicator - tight spacing matching reference image
                if self._right_mode == "wave":
                    # Dynamic responsive audio wave bars (tight red vertical bars)
                    wave_pen = gdi32.CreatePen(0, 2, self._accent_color_bgr)
                    prev_wp = gdi32.SelectObject(mem_dc, wave_pen)
                    center_y = height // 2

                    lvl = self._smoothed_level
                    # Multipliers give clean voice wave shape
                    bar_multipliers = [0.4, 0.75, 1.0, 0.8, 0.45]
                    min_bar_h = 4
                    max_bar_h = 24

                    # Position waveform on the right with tight gap
                    start_x = width - 48
                    for idx, mult in enumerate(bar_multipliers):
                        h_val = int(min_bar_h + (max_bar_h - min_bar_h) * lvl * mult)
                        h_val = max(min_bar_h, min(h_val, max_bar_h))
                        bx = start_x + (idx * 5)
                        by1 = center_y - (h_val // 2)
                        by2 = center_y + (h_val // 2)
                        gdi32.MoveToEx(mem_dc, bx, by1, None)
                        gdi32.LineTo(mem_dc, bx, by2)

                    gdi32.SelectObject(mem_dc, prev_wp)
                    gdi32.DeleteObject(wave_pen)

                elif self._right_mode == "spinner":
                    # Circular amber loading spinner on the right
                    spinner_pen = gdi32.CreatePen(0, 2, self._accent_color_bgr)
                    prev_sp = gdi32.SelectObject(mem_dc, spinner_pen)

                    cx = width - 32
                    cy = height // 2
                    radius = 8

                    ang = self._spinner_angle
                    # Arc spanning ~270 degrees (4.7 rad)
                    x1 = int(cx + radius * math.cos(ang))
                    y1 = int(cy + radius * math.sin(ang))
                    x2 = int(cx + radius * math.cos(ang + 4.7))
                    y2 = int(cy + radius * math.sin(ang + 4.7))

                    gdi32.Arc(mem_dc, cx - radius, cy - radius, cx + radius, cy + radius, x1, y1, x2, y2)

                    gdi32.SelectObject(mem_dc, prev_sp)
                    gdi32.DeleteObject(spinner_pen)

                elif self._right_mode in ("check", "error"):
                    # Symbol icon on right
                    if not self._font_icon:
                        self._font_icon = gdi32.CreateFontW(
                            18, 0, 0, 0, 700, False, False, False,
                            1, 0, 0, 5, 0, "Segoe UI"
                        )
                    gdi32.SelectObject(mem_dc, self._font_icon)
                    gdi32.SetTextColor(mem_dc, self._accent_color_bgr)
                    icon_text = "✓" if self._right_mode == "check" else "⚠"
                    right_rect = RECT(width - 40, 0, width - 14, height)
                    user32.DrawTextW(
                        mem_dc, icon_text, -1, ctypes.byref(right_rect),
                        DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX
                    )

                # Blit to window DC
                gdi32.BitBlt(hdc, 0, 0, width, height, mem_dc, 0, 0, 0x00CC0020) # SRCCOPY

                # Cleanup DC objects
                gdi32.SelectObject(mem_dc, old_pen)
                gdi32.SelectObject(mem_dc, old_brush)
                gdi32.SelectObject(mem_dc, old_font)
                gdi32.SelectObject(mem_dc, old_bm)
                gdi32.DeleteObject(border_pen)
                gdi32.DeleteObject(bg_brush)
                gdi32.DeleteObject(mem_bm)
                gdi32.DeleteDC(mem_dc)

                user32.EndPaint(hwnd, ctypes.byref(ps))
                return 0
            elif msg == WM_UPDATE_STATUS:
                # Update pill size dynamically if state changed
                user32.SetWindowPos(
                    hwnd, HWND_TOPMOST,
                    self._target_x, self._target_y, self._pill_width, self._pill_height,
                    SWP_NOACTIVATE | SWP_SHOWWINDOW
                )
                # Re-apply matching rounded region
                rgn = gdi32.CreateRoundRectRgn(0, 0, self._pill_width, self._pill_height, 24, 24)
                user32.SetWindowRgn(hwnd, rgn, True)
                user32.InvalidateRect(hwnd, None, True)
                return 0
            elif msg == WM_ANIM_TICK:
                user32.InvalidateRect(hwnd, None, False)
                return 0
            elif msg == WM_HIDE_STATUS:
                user32.ShowWindow(hwnd, SW_HIDE)
                return 0
            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            try:
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
            except Exception:
                return 0

        self._wndproc_ref = WNDPROC(wndproc)

        wndclass = WNDCLASSEXW()
        wndclass.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wndclass.style = CS_HREDRAW | CS_VREDRAW | CS_DROPSHADOW
        wndclass.lpfnWndProc = ctypes.cast(self._wndproc_ref, ctypes.c_void_p).value
        wndclass.hInstance = hinst
        wndclass.lpszClassName = class_name
        wndclass.hCursor = user32.LoadCursorW(None, 32512)  # IDC_ARROW

        user32.RegisterClassExW(ctypes.byref(wndclass))

        # Initial geometry
        width = self._pill_width
        height = self._pill_height
        x, y = self._calculate_monitor_pos(0)
        self._target_x = x
        self._target_y = y

        ex_style = WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self._hwnd = user32.CreateWindowExW(
            ex_style,
            class_name,
            "OpenFlow Status",
            WS_POPUP,
            x, y, width, height,
            None, None, hinst, None
        )

        if self._hwnd:
            rgn = gdi32.CreateRoundRectRgn(0, 0, width, height, 24, 24)
            user32.SetWindowRgn(self._hwnd, rgn, True)

        self._ready_event.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def update_audio_level(self, rms: float):
        """Called from audio callback with fresh block RMS. Thread-safe and non-blocking."""
        if self._right_mode != "wave":
            return
        # Normalize: voice typically sits in 0.005 to 0.12 range
        norm = min(1.0, max(0.0, (rms - 0.003) / 0.08))
        self._target_level = norm

    def _start_animation_loop(self):
        with self._lock:
            if self._anim_running:
                return
            self._anim_running = True
            self._anim_thread = threading.Thread(target=self._anim_worker, daemon=True)
            self._anim_thread.start()

    def _stop_animation_loop(self):
        with self._lock:
            self._anim_running = False

    def _anim_worker(self):
        """Lightweight 30 FPS animation loop for audio waveform attack/release and spinner rotation."""
        while True:
            with self._lock:
                if not self._anim_running:
                    break
                mode = self._right_mode

            if mode == "wave":
                # Smooth audio level: fast attack (0.45), smooth release (0.15)
                target = self._target_level
                current = self._smoothed_level
                if target > current:
                    current += (target - current) * 0.45 # attack
                else:
                    current += (target - current) * 0.15 # release
                self._smoothed_level = current

                if self._hwnd:
                    user32.PostMessageW(self._hwnd, WM_ANIM_TICK, 0, 0)

            elif mode == "spinner":
                # Smooth rotation step (rad/tick)
                self._spinner_angle = (self._spinner_angle + 0.35) % (2 * math.pi)
                if self._hwnd:
                    user32.PostMessageW(self._hwnd, WM_ANIM_TICK, 0, 0)
            else:
                break

            time.sleep(0.033) # ~30 FPS

    def _update_ui(self, label: str, pill_width: int, dot_bgr: int, border_bgr: int, bg_bgr: int, right_mode: str, accent_bgr: int):
        with self._lock:
            self._state_label = label
            self._pill_width = pill_width
            self._dot_color_bgr = dot_bgr
            self._border_color_bgr = border_bgr
            self._bg_color_bgr = bg_bgr
            self._right_mode = right_mode
            self._accent_color_bgr = accent_bgr

        if right_mode in ("wave", "spinner"):
            self._start_animation_loop()
        else:
            self._stop_animation_loop()

        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_UPDATE_STATUS, 0, 0)

    def _hide_ui(self):
        self._stop_animation_loop()
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_HIDE_STATUS, 0, 0)

    def show_listening(self, target_hwnd: int = 0):
        """
        Shows Listening pill matching the visual specification:
        - Pale pink fill (#FFF0F2) + vibrant red border (#EF4444)
        - Red status dot + 'Listening' label
        - Red animated waveform bars on right
        """
        with self._lock:
            if self._hide_timer:
                self._hide_timer.cancel()
                self._hide_timer = None
            self._pill_width = 226
            x, y = self._calculate_monitor_pos(target_hwnd)
            self._target_x = x
            self._target_y = y
            self._target_level = 0.0
            self._smoothed_level = 0.0

        # Colors (BGR):
        # dot: RGB(239, 68, 68) -> 0x004444EF
        # border: RGB(239, 68, 68) -> 0x004444EF
        # bg: RGB(254, 242, 242) -> 0x00F2F2FE (pale translucent pink)
        # accent: RGB(239, 68, 68) -> 0x004444EF
        self._update_ui(
            label="Listening",
            pill_width=226,
            dot_bgr=0x004444EF,
            border_bgr=0x004444EF,
            bg_bgr=0x00F2F2FE,
            right_mode="wave",
            accent_bgr=0x004444EF
        )

    def show_transcribing(self):
        """
        Shows Transcribing pill matching the visual specification:
        - Pale cream/yellow fill (#FEF9EE) + amber border (#F59E0B)
        - Amber status dot + 'Transcribing' label
        - Circular amber spinner smoothly rotating on right
        """
        with self._lock:
            if self._hide_timer:
                self._hide_timer.cancel()
                self._hide_timer = None
            self._pill_width = 246
            self._spinner_angle = 0.0

        # Colors (BGR):
        # dot: RGB(245, 158, 11) -> 0x000B9EF5
        # border: RGB(245, 158, 11) -> 0x000B9EF5
        # bg: RGB(254, 249, 238) -> 0x00EEF9FE (pale cream yellow)
        # accent: RGB(245, 158, 11) -> 0x000B9EF5
        self._update_ui(
            label="Transcribing",
            pill_width=246,
            dot_bgr=0x000B9EF5,
            border_bgr=0x000B9EF5,
            bg_bgr=0x00EEF9FE,
            right_mode="spinner",
            accent_bgr=0x000B9EF5
        )

    def show_success(self, message: str = "Text inserted"):
        """Shows success indicator with green dot, pale emerald fill, and checkmark, automatically hiding after 1.5s."""
        # dot & border: RGB(16, 185, 129) -> 0x0081B910
        # bg: RGB(236, 253, 245) -> 0x00F5FDEC
        self._update_ui(
            label=message,
            pill_width=240,
            dot_bgr=0x0081B910,
            border_bgr=0x0081B910,
            bg_bgr=0x00F5FDEC,
            right_mode="check",
            accent_bgr=0x0081B910
        )
        self._schedule_hide(1.5)

    def show_error(self, message: str = "Error"):
        """Shows error indicator and hides after 2.5s."""
        self._update_ui(
            label=message,
            pill_width=220,
            dot_bgr=0x003232DC,
            border_bgr=0x003232DC,
            bg_bgr=0x00F2F2FE,
            right_mode="error",
            accent_bgr=0x003232DC
        )
        self._schedule_hide(2.5)

    def _schedule_hide(self, delay: float):
        with self._lock:
            if self._hide_timer:
                self._hide_timer.cancel()
            self._hide_timer = threading.Timer(delay, self._hide_ui)
            self._hide_timer.daemon = True
            self._hide_timer.start()

    def close(self):
        """Clean shutdown of Win32 overlay resources."""
        self._stop_animation_loop()
        with self._lock:
            if self._hide_timer:
                self._hide_timer.cancel()
                self._hide_timer = None
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_DESTROY, 0, 0)
            self._hwnd = None
        if self._font_label:
            gdi32.DeleteObject(self._font_label)
            self._font_label = None
        if self._font_icon:
            gdi32.DeleteObject(self._font_icon)
            self._font_icon = None
