import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import threading
import time
import json
import os
import sys
import win32api
import win32gui
import win32process
import win32con
import pywintypes
import psutil
import pywinauto
from pywinauto.application import Application
import pystray
from PIL import Image
import ctypes
from ctypes import wintypes

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    RESOURCE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = APP_DIR

CONFIG_PATH = os.path.join(APP_DIR, "config.json")
TRAY_ICON_PATH = os.path.join(RESOURCE_DIR, "icon.ico")
VK_CONTROL = 0x11
VK_S = 0x53
CTRL_S_TRIGGER_DELAY_MS = 500
WM_TRAYICON = win32con.WM_USER + 20
TRAY_UID = 1
ID_TRAY_SHOW = 1000
ID_TRAY_EXIT = 1001

# 未设置自定义记录时使用的默认布局。坐标使用 Windows 虚拟桌面坐标，
# 当前机器上 DISPLAY2 位于主屏左侧，因此 X 坐标为负数。
DEFAULT_WINDOW_LAYOUT = {
    "m2server": {
        "screen": r"\\.\DISPLAY2",
        "x": -760,
        "y": 5,
        "width": 754,
        "height": 516,
    },
    "client_console": {
        "screen": r"\\.\DISPLAY2",
        "x": -765,
        "y": 517,
        "width": 759,
        "height": 519,
    },
}
CLIENT_CONSOLE_TITLE = r"E:\龙龙火龙七改\client\game.exe"
CLIENT_CONSOLE_EXE = os.path.normcase(os.path.normpath(CLIENT_CONSOLE_TITLE))
_app = None

def tray_wnd_proc(hwnd, msg, wparam, lparam):
    global _app
    if msg == WM_TRAYICON:
        event = lparam & 0xFFFF
        if event in (win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP, win32con.WM_CONTEXTMENU):
            if _app:
                _app.show_tray_menu()
        elif event == win32con.WM_LBUTTONDBLCLK:
            if _app:
                _app.show_main_window()
        return 0
    elif msg == win32con.WM_COMMAND:
        cmd = wparam & 0xFFFF
        if cmd == ID_TRAY_SHOW:
            if _app:
                _app.show_main_window()
            return 0
        if cmd == ID_TRAY_EXIT:
            if _app:
                _app.exit_app()
            return 0
    elif msg == win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
        return 0
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

class LOGFONTW(ctypes.Structure):
    _fields_ = [("lfHeight", wintypes.LONG), ("lfWidth", wintypes.LONG),
        ("lfEscapement", wintypes.LONG), ("lfOrientation", wintypes.LONG),
        ("lfWeight", wintypes.LONG), ("lfItalic", wintypes.BYTE),
        ("lfUnderline", wintypes.BYTE), ("lfStrikeOut", wintypes.BYTE),
        ("lfCharSet", wintypes.BYTE), ("lfOutPrecision", wintypes.BYTE),
        ("lfClipPrecision", wintypes.BYTE), ("lfQuality", wintypes.BYTE),
        ("lfPitchAndFamily", wintypes.BYTE), ("lfFaceName", wintypes.WCHAR * 32)]

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

FONTS = [
    "Consolas", "Lucida Console", "Tahoma",
    "微软雅黑", "宋体", "黑体", "新宋体",
    "Cascadia Code", "Cascadia Mono", "Courier New",
    "Fixedsys", "Segoe UI", "Arial",
]

class App:
    def __init__(self):
        global _app
        _app = self
        self.running = True
        self.tray_running = True
        self.tray_hwnd = None
        self.tray_hicon = None
        self.tray_icon = None
        self.m2_pid = None
        self.m2_hwnd = None
        self.check_vars = {}

        cfg = load_config()
        self.cfg_font = cfg.get("font_name", "Segoe UI")
        self.cfg_size = cfg.get("font_size", "22")
        self._font_cache = {}
        self._auto_font_after_id = None

        self.root = tk.Tk()
        self.root.title("M2Server 重载管理 By:老刀 QQ:1556666987")
        self.root.geometry("480x580")
        self.root.resizable(False, True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.withdraw()  # 启动后默认只显示托盘图标

        self.build_ui()
        self.load_data()
        self.start_polling()
        self.start_tray_icon()
        self._start_auto_font()
        # 启动时立即恢复窗口布局；Ctrl+S 时还会再次恢复，适配目标程序重启或移动。
        self.root.after(100, self._restore_window_layout)

        self.root.mainloop()

    def build_ui(self):
        ttk.Label(
            self.root,
            text="重新加载子项（Ctrl+S 触发执行）",
            font=("", 11, "bold"),
        ).pack(pady=(10, 5))

        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="全选", command=self.select_all, width=10).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="取消全选", command=self.deselect_all, width=10).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="退出", command=self.exit_app, width=8).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="刷新", command=self.refresh, width=8).pack(side="right", padx=2)

        layout_frame = ttk.Frame(self.root)
        layout_frame.pack(fill="x", padx=10, pady=(0, 5))
        ttk.Button(layout_frame, text="记录窗口", command=self.record_windows, width=10).pack(side="left", padx=2)
        ttk.Button(layout_frame, text="清除记录", command=self.clear_window_record, width=10).pack(side="left", padx=2)
        ttk.Label(layout_frame, text="Ctrl+S 时自动恢复窗口布局").pack(side="left", padx=(10, 2))

        container = ttk.Frame(self.root)
        container.pack(fill="both", expand=True, padx=10, pady=5)

        canvas = tk.Canvas(container, highlightthickness=0, bg="#f0f0f0")
        self.items_canvas = canvas
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.items_frame = ttk.Frame(canvas)

        self.items_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.items_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.items_frame.bind("<MouseWheel>", self._on_mousewheel)

        # 字体设置区域
        font_frame = ttk.LabelFrame(self.root, text="日志窗口字体设置", padding=10)
        font_frame.pack(fill="x", padx=10, pady=5)

        row1 = ttk.Frame(font_frame)
        row1.pack(fill="x")
        ttk.Label(row1, text="字体:").pack(side="left")
        self.font_var = tk.StringVar(value=self.cfg_font)
        self.font_combo = ttk.Combobox(row1, textvariable=self.font_var, values=FONTS, width=20, state="readonly")
        self.font_combo.pack(side="left", padx=(5, 15))

        ttk.Label(row1, text="大小:").pack(side="left")
        self.size_var = tk.StringVar(value=self.cfg_size)
        self.size_entry = ttk.Entry(row1, textvariable=self.size_var, width=6)
        self.size_entry.pack(side="left", padx=(5, 10))

        ttk.Button(row1, text="修改字体", command=self.apply_font).pack(side="left", padx=5)

        row2 = ttk.Frame(font_frame)
        row2.pack(fill="x", pady=(5, 0))
        self.auto_font_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="每秒自动枚举窗口并应用字体", variable=self.auto_font_var, command=self._on_auto_font_toggle).pack(side="left")

        # 状态栏
        self.status_var = tk.StringVar(value="就绪，等待 Ctrl+S...")
        ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 10))

    def _on_mousewheel(self, event):
        self.items_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def apply_font(self):
        font_name = self.font_var.get()
        try:
            font_size = int(self.size_var.get())
        except:
            self.status_var.set("字体大小必须为数字")
            return

        if not self._refresh_connection():
            self.status_var.set("未连接到 M2Server，请先刷新")
            return

        target_memo = self._find_memo(self.m2_hwnd)
        if not target_memo:
            self.status_var.set("未找到日志编辑器(TMemo)")
            return

        if self._do_apply_font(target_memo, font_name, font_size):
            cfg = load_config()
            cfg["font_name"] = font_name
            cfg["font_size"] = font_size
            save_config(cfg)
            self.cfg_font, self.cfg_size = font_name, str(font_size)
            self.status_var.set(f"字体已更新: {font_name} {font_size}")
        else:
            self.status_var.set("创建字体失败")

    def _find_memo(self, parent_hwnd):
        target_memo = None
        def find(hwnd):
            nonlocal target_memo
            if win32gui.GetClassName(hwnd) == "TMemo":
                target_memo = hwnd
                return False
            def cb(c, _):
                find(c)
                return True
            win32gui.EnumChildWindows(hwnd, cb, None)
        find(parent_hwnd)
        return target_memo

    def _do_apply_font(self, memo_hwnd, font_name, font_size):
        lf = LOGFONTW()
        lf.lfHeight = -font_size
        lf.lfCharSet = 134
        lf.lfFaceName = font_name
        hfont = ctypes.windll.gdi32.CreateFontIndirectW(ctypes.byref(lf))
        if hfont:
            ctypes.windll.user32.SendMessageW(memo_hwnd, 0x0030, hfont, 1)
            ctypes.windll.user32.InvalidateRect(memo_hwnd, None, True)
            return True
        return False

    def _start_auto_font(self):
        self._auto_font_tick()

    def _auto_font_tick(self):
        if not self.auto_font_var.get():
            self._auto_font_after_id = self.root.after(1000, self._auto_font_tick)
            return

        font_name = self.cfg_font
        try:
            font_size = int(self.cfg_size)
        except:
            self._auto_font_after_id = self.root.after(1000, self._auto_font_tick)
            return

        hwnds = []
        def enum_cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and "996引擎" in title and "KUAFU" in title:
                    hwnds.append(hwnd)
            return True
        win32gui.EnumWindows(enum_cb, None)

        applied = 0
        for hwnd in hwnds:
            memo = self._find_memo(hwnd)
            if not memo:
                continue
            cache_key = (hwnd, font_name, font_size)
            if self._font_cache.get(hwnd) == cache_key:
                continue
            if self._do_apply_font(memo, font_name, font_size):
                self._font_cache[hwnd] = cache_key
                applied += 1

        stale = [h for h in self._font_cache if not win32gui.IsWindow(h)]
        for h in stale:
            del self._font_cache[h]

        if applied:
            self.status_var.set(f"自动字体: 已应用 {applied} 个窗口")

        self._auto_font_after_id = self.root.after(1000, self._auto_font_tick)

    def _on_auto_font_toggle(self):
        if self.auto_font_var.get():
            self._font_cache.clear()
            self.status_var.set("自动字体设置已开启")
        else:
            self.status_var.set("自动字体设置已关闭")

    def _save_selected(self):
        selected = [t for t, v in self.check_vars.items() if v.get()]
        cfg = load_config()
        cfg["selected_items"] = selected
        save_config(cfg)

    def _on_check_changed(self, *args):
        self._save_selected()

    def select_all(self):
        for v in self.check_vars.values():
            v.set(True)
        self._save_selected()

    def deselect_all(self):
        for v in self.check_vars.values():
            v.set(False)
        self._save_selected()

    def refresh(self):
        self.load_data()

    @staticmethod
    def _copy_default_layout():
        return {
            key: value.copy()
            for key, value in DEFAULT_WINDOW_LAYOUT.items()
        }

    def _process_matches(self, hwnd, expected_name, expected_path=None):
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            if process.name().lower() != expected_name.lower():
                return False
            if expected_path:
                try:
                    actual_path = os.path.normcase(os.path.normpath(process.exe()))
                except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                    actual_path = ""
                if actual_path and actual_path != expected_path:
                    return False
            return True
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess, OSError):
            return False

    def _find_target_windows(self, require_visible=True):
        targets = {"m2server": None, "client_console": None}

        def enum_cb(hwnd, _):
            try:
                # 记录模式跳过隐藏/最小化窗口，避免把 -32000 坐标写入配置；恢复
                # 模式允许找到最小化窗口，再先恢复其正常状态后设置布局。
                if not win32gui.IsWindow(hwnd):
                    return True
                if require_visible and (not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd)):
                    return True
                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return True

                if (
                    targets["m2server"] is None
                    and "996引擎" in title
                    and "KUAFU" in title
                    and self._process_matches(hwnd, "M2Server.exe")
                ):
                    targets["m2server"] = hwnd

                if (
                    targets["client_console"] is None
                    and title == CLIENT_CONSOLE_TITLE
                    and self._process_matches(hwnd, "game.exe", CLIENT_CONSOLE_EXE)
                ):
                    targets["client_console"] = hwnd
            except Exception:
                return True
            return targets["m2server"] is None or targets["client_console"] is None

        try:
            win32gui.EnumWindows(enum_cb, None)
        except pywintypes.error:
            # 窗口在枚举期间被关闭时，EnumWindows 可能返回系统错误；保留
            # 已经找到的句柄，由调用方决定是否继续或提示缺失。
            pass
        return targets

    @staticmethod
    def _window_layout_info(hwnd):
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        monitor_info = win32api.GetMonitorInfo(monitor)
        return {
            "screen": monitor_info.get("Device", ""),
            "x": int(left),
            "y": int(top),
            "width": int(right - left),
            "height": int(bottom - top),
        }

    @staticmethod
    def _monitor_work_area(device_name):
        for monitor_handle, _, _ in win32api.EnumDisplayMonitors():
            info = win32api.GetMonitorInfo(monitor_handle)
            if info.get("Device") == device_name:
                return info.get("Work", info.get("Monitor"))
        return None

    @staticmethod
    def _sync_console_buffer(hwnd, client_width, client_height):
        """Synchronize a classic console buffer with its resized pixel viewport."""
        if win32gui.GetClassName(hwnd) != "ConsoleWindowClass":
            return

        kernel32 = ctypes.windll.kernel32
        kernel32.GetConsoleWindow.restype = wintypes.HWND
        # The GUI app normally has no console of its own. Avoid stealing an
        # interactive console when the script is launched from a terminal.
        if kernel32.GetConsoleWindow():
            return

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not kernel32.AttachConsole(pid):
            return

        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        OPEN_EXISTING = 3
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        class COORD(ctypes.Structure):
            _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

        class SMALL_RECT(ctypes.Structure):
            _fields_ = [
                ("Left", wintypes.SHORT),
                ("Top", wintypes.SHORT),
                ("Right", wintypes.SHORT),
                ("Bottom", wintypes.SHORT),
            ]

        class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
            _fields_ = [
                ("dwSize", COORD),
                ("dwCursorPosition", COORD),
                ("wAttributes", wintypes.WORD),
                ("srWindow", SMALL_RECT),
                ("dwMaximumWindowSize", COORD),
            ]

        class CONSOLE_FONT_INFO(ctypes.Structure):
            _fields_ = [("nFont", wintypes.DWORD), ("dwFontSize", COORD)]

        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.GetConsoleScreenBufferInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(CONSOLE_SCREEN_BUFFER_INFO),
        ]
        kernel32.GetConsoleScreenBufferInfo.restype = wintypes.BOOL
        kernel32.SetConsoleWindowInfo.argtypes = [
            wintypes.HANDLE,
            wintypes.BOOL,
            ctypes.POINTER(SMALL_RECT),
        ]
        kernel32.SetConsoleWindowInfo.restype = wintypes.BOOL
        kernel32.SetConsoleScreenBufferSize.argtypes = [wintypes.HANDLE, COORD]
        kernel32.SetConsoleScreenBufferSize.restype = wintypes.BOOL
        kernel32.GetCurrentConsoleFont.argtypes = [
            wintypes.HANDLE,
            wintypes.BOOL,
            ctypes.POINTER(CONSOLE_FONT_INFO),
        ]
        kernel32.GetCurrentConsoleFont.restype = wintypes.BOOL

        handle = kernel32.CreateFileW(
            "CONOUT$",
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if handle == INVALID_HANDLE_VALUE:
            kernel32.FreeConsole()
            return

        try:
            info = CONSOLE_SCREEN_BUFFER_INFO()
            if not kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
                return

            # Classic console dimensions are character-based. Use the active
            # font metrics to convert the pixel client area into columns/rows.
            font_info = CONSOLE_FONT_INFO()
            if kernel32.GetCurrentConsoleFont(handle, False, ctypes.byref(font_info)):
                cell_width = max(1, int(font_info.dwFontSize.X))
                cell_height = max(1, int(font_info.dwFontSize.Y))
            else:
                cell_width, cell_height = 8, 16
            columns = max(1, int(client_width / cell_width))
            rows = max(1, int(client_height / cell_height))

            # Do not use GetScrollInfo().nPage here. During a resize conhost
            # can briefly report the previous (or a horizontally scrolled)
            # viewport page. Treating that stale value as the target width can
            # shrink the character buffer and make the whole console window
            # narrower than the requested layout. The resized client area and
            # current font metrics provide a stable target instead.
            columns = min(columns, 32767)
            rows = min(rows, 32767)

            buffer_width = max(columns, int(info.dwCursorPosition.X) + 1)
            buffer_height = max(int(info.dwSize.Y), int(info.srWindow.Top) + rows)
            current_top = max(0, min(int(info.srWindow.Top), buffer_height - rows))

            # A larger viewport needs a larger buffer first. When narrowing,
            # the viewport must fit the existing buffer before the buffer can
            # be reduced to the target width.
            if buffer_width > int(info.dwSize.X) or buffer_height > int(info.dwSize.Y):
                if not kernel32.SetConsoleScreenBufferSize(handle, COORD(buffer_width, buffer_height)):
                    return
            viewport = SMALL_RECT(0, current_top, columns - 1, current_top + rows - 1)
            if not kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(viewport)):
                return
            if buffer_width < int(info.dwSize.X) or buffer_height < int(info.dwSize.Y):
                kernel32.SetConsoleScreenBufferSize(handle, COORD(buffer_width, buffer_height))
        finally:
            kernel32.CloseHandle(handle)
            kernel32.FreeConsole()

    def _clamped_window_position(self, geometry):
        width = max(1, int(geometry["width"]))
        height = max(1, int(geometry["height"]))
        x = int(geometry["x"])
        y = int(geometry["y"])
        work_area = self._monitor_work_area(geometry.get("screen", ""))
        if work_area:
            left, top, right, bottom = work_area
            max_x = max(left, right - width)
            max_y = max(top, bottom - height)
            x = min(max(x, left), max_x)
            y = min(max(y, top), max_y)
        return x, y, width, height

    def record_windows(self):
        targets = self._find_target_windows()
        missing = []
        if not targets["m2server"]:
            missing.append("M2Server 主窗口")
        if not targets["client_console"]:
            missing.append("客户端控制台窗口")
        if missing:
            messagebox.showwarning(
                "无法记录窗口",
                "以下窗口未找到，已中止记录：\n" + "、".join(missing),
                parent=self.root,
            )
            self.status_var.set("记录窗口失败：两个目标窗口必须同时存在")
            return

        cfg = load_config()
        cfg["window_layout"] = {
            "m2server": self._window_layout_info(targets["m2server"]),
            "client_console": self._window_layout_info(targets["client_console"]),
        }
        if save_config(cfg):
            self.status_var.set("已记录 M2Server 和客户端控制台窗口布局")
        else:
            self.status_var.set("窗口布局保存失败，请检查配置文件权限")

    def clear_window_record(self):
        cfg = load_config()
        if "window_layout" in cfg:
            del cfg["window_layout"]
        if save_config(cfg):
            self.status_var.set("已清除自定义窗口布局，将使用默认布局")
        else:
            self.status_var.set("清除窗口布局失败，请检查配置文件权限")

    def _active_window_layout(self):
        layout = self._copy_default_layout()
        custom = load_config().get("window_layout")
        if not isinstance(custom, dict):
            return layout
        for key in layout:
            value = custom.get(key)
            if not isinstance(value, dict):
                continue
            for field in ("screen", "x", "y", "width", "height"):
                if field in value:
                    layout[key][field] = value[field]
        return layout

    def _restore_window_layout(self):
        targets = self._find_target_windows(require_visible=False)
        layout = self._active_window_layout()
        restored = []
        missing = []
        for key, label in (("m2server", "M2Server"), ("client_console", "客户端控制台")):
            hwnd = targets.get(key)
            if not hwnd:
                missing.append(label)
                continue
            geometry = layout[key]
            try:
                x, y, width, height = self._clamped_window_position(geometry)
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                elif not win32gui.IsWindowVisible(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
                win32gui.SetWindowPos(
                    hwnd,
                    0,
                    x,
                    y,
                    width,
                    height,
                    win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED,
                )
                # WM_SIZE 的 lParam 要求客户区尺寸，而不是包含边框的外框尺寸。
                # 手动拖动窗口时 Windows 也会按客户区尺寸发送该消息。
                _, _, client_width, client_height = win32gui.GetClientRect(hwnd)
                size_lparam = win32api.MAKELONG(client_width, client_height)
                win32gui.SendMessage(hwnd, win32con.WM_SIZE, win32con.SIZE_RESTORED, size_lparam)
                win32gui.InvalidateRect(hwnd, None, True)
                win32gui.UpdateWindow(hwnd)
                if win32gui.GetClassName(hwnd) == "ConsoleWindowClass":
                    self._sync_console_buffer(hwnd, client_width, client_height)
                    # conhost may recalculate its viewport asynchronously in
                    # response to WM_SIZE. Repeat after that pass and repaint.
                    self.root.after(100, self._resync_console_window, hwnd)
                    self.root.after(300, self._resync_console_window, hwnd)
                restored.append(label)
            except (KeyError, TypeError, ValueError, OSError):
                missing.append(label)

        if missing:
            self.status_var.set(
                "窗口布局：已调整 " + ("、".join(restored) if restored else "无")
                + "；未找到或调整失败：" + "、".join(missing)
            )
        elif restored:
            self.status_var.set("窗口布局已恢复：" + "、".join(restored))
        return targets

    def _resync_console_window(self, hwnd):
        if not win32gui.IsWindow(hwnd) or win32gui.GetClassName(hwnd) != "ConsoleWindowClass":
            return
        try:
            _, _, client_width, client_height = win32gui.GetClientRect(hwnd)
            self._sync_console_buffer(hwnd, client_width, client_height)
            win32gui.InvalidateRect(hwnd, None, True)
            win32gui.UpdateWindow(hwnd)
        except (OSError, pywintypes.error):
            pass

    def load_data(self):
        for w in self.items_frame.winfo_children():
            w.destroy()
        self.check_vars.clear()

        self.status_var.set("正在获取菜单...")
        self.root.update()

        items = self._fetch_reload_items()
        cfg = load_config()
        saved_selected = cfg.get("selected_items")
        has_saved = bool(saved_selected)

        default_prefixes = [
            "物品数据", "怪物数据(&K)", "重载爆率", "重载套装",
            "&Buff", "LuaFunc函数库", "LuaCond条件函数库",
            "&QFunction", "Q&Manage", "重载机器人", "所有NPC",
        ]

        for text in items:
            if has_saved:
                checked = text in saved_selected
            else:
                checked = any(text.startswith(p) or p in text for p in default_prefixes)
            var = tk.BooleanVar(value=checked)
            var.trace_add("write", self._on_check_changed)
            cb = ttk.Checkbutton(self.items_frame, text=text, variable=var)
            cb.pack(anchor="w", padx=5, pady=1)
            cb.bind("<MouseWheel>", self._on_mousewheel)
            self.check_vars[text] = var

        if not items:
            self.status_var.set("未找到 M2Server 窗口或重新加载子项")
        else:
            cnt = sum(1 for v in self.check_vars.values() if v.get())
            self.status_var.set(f"就绪，共 {len(items)} 项（已勾选 {cnt} 项），等待 Ctrl+S...")

    def _fetch_reload_items(self):
        target_hwnd = self._find_target_windows(require_visible=True).get("m2server")
        if not target_hwnd:
            return []

        self.m2_hwnd = target_hwnd
        _, pid = win32process.GetWindowThreadProcessId(self.m2_hwnd)
        try:
            pname = psutil.Process(pid).name()
            if pname.lower() != "m2server.exe":
                return []
        except:
            return []

        self.m2_pid = pid

        try:
            app = Application(backend="win32").connect(process=pid)
            dlg = app.window(title_re=".*996引擎.*KUAFU.*")

            for item in dlg.menu().items():
                if "控制" in item.text():
                    for sub in item.sub_menu().items():
                        if "重新加载" in sub.text():
                            return [r.text() for r in sub.sub_menu().items() if r.text().strip()]
        except:
            pass

        return []

    def start_polling(self):
        self.poll_running = True
        self.ctrl_s_was_pressed = False
        self._last_trigger = 0.0
        t = threading.Thread(target=self._poll_thread, daemon=True)
        t.start()

    def _poll_thread(self):
        ctypes.windll.user32.GetAsyncKeyState.restype = ctypes.c_short

        while self.poll_running:
            ctrl_down = bool(ctypes.windll.user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
            s_down = bool(ctypes.windll.user32.GetAsyncKeyState(VK_S) & 0x8000)
            now_pressed = ctrl_down and s_down

            if now_pressed and not self.ctrl_s_was_pressed:
                now = time.time()
                if now - self._last_trigger >= 1.0:
                    self._last_trigger = now
                    self.root.after(CTRL_S_TRIGGER_DELAY_MS, self.execute_checked)

            self.ctrl_s_was_pressed = now_pressed
            time.sleep(0.05)

    def _refresh_connection(self):
        target_hwnd = self._find_target_windows(require_visible=True).get("m2server")
        if not target_hwnd:
            return False
        self.m2_hwnd = target_hwnd
        _, pid = win32process.GetWindowThreadProcessId(self.m2_hwnd)
        try:
            pname = psutil.Process(pid).name()
            if pname.lower() != "m2server.exe":
                return False
        except:
            return False
        self.m2_pid = pid
        return True

    def execute_checked(self):
        # Ctrl+S 时先恢复两个目标窗口布局，即使当前没有勾选重载项也执行。
        self._restore_window_layout()
        checked = [t for t, v in self.check_vars.items() if v.get()]
        if not checked:
            self.status_var.set("没有选中任何项目")
            return

        # 每次执行前重新扫描窗口句柄（防止M2重启后句柄过期）
        if not self._refresh_connection():
            self.status_var.set("未连接到 M2Server，请先刷新")
            return

        self.status_var.set(f"正在执行 {len(checked)} 个项目...")
        self.root.update()

        try:
            app = Application(backend="win32").connect(process=self.m2_pid)
            dlg = app.window(title_re=".*996引擎.*KUAFU.*")

            for item in dlg.menu().items():
                if "控制" in item.text():
                    for sub in item.sub_menu().items():
                        if "重新加载" in sub.text():
                            reload_menu = sub.sub_menu()
                            if not reload_menu:
                                continue

                            for target_text in checked:
                                for r in reload_menu.items():
                                    if target_text in r.text():
                                        mid = r.item_id()
                                        win32gui.PostMessage(self.m2_hwnd, win32con.WM_COMMAND, mid, 0)
                                        self.status_var.set(f"执行: {target_text}")
                                        self.root.update()
                                        time.sleep(0.3)
                                        break

                            self.status_var.set("任务完成")
                            return

            self.status_var.set("未找到重新加载菜单")
        except Exception as e:
            self.status_var.set(f"执行失败: {e}")

    def start_tray_icon(self):
        t = threading.Thread(target=self._tray_thread, daemon=True)
        t.start()

    def _tray_thread(self):
        try:
            image = Image.open(TRAY_ICON_PATH)
        except:
            image = Image.new("RGB", (64, 64), "#2f6fed")

        menu = pystray.Menu(
            pystray.MenuItem("显示", lambda icon, item: self.show_main_window(), default=True),
            pystray.MenuItem("退出", lambda icon, item: self.exit_app()),
        )
        self.tray_icon = pystray.Icon("M2ServerReload", image, "M2Server 重载管理", menu)
        self.tray_icon.run()

    def show_main_window(self):
        if self.root.winfo_exists():
            self.root.after(0, self._show_main_window)

    def _show_main_window(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(100, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    def show_tray_menu(self):
        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(menu, win32con.MF_STRING, ID_TRAY_SHOW, "显示")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, None)
        win32gui.AppendMenu(menu, win32con.MF_STRING, ID_TRAY_EXIT, "退出")
        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self.tray_hwnd)
        cmd = win32gui.TrackPopupMenu(
            menu,
            win32con.TPM_RIGHTBUTTON | 0x0100,  # TPM_RETURNCMD
            pos[0], pos[1], 0, self.tray_hwnd, None
        )
        win32gui.PostMessage(self.tray_hwnd, win32con.WM_NULL, 0, 0)
        if cmd == ID_TRAY_SHOW:
            self.show_main_window()
        elif cmd == ID_TRAY_EXIT:
            self.exit_app()

    def remove_tray_icon(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except:
                pass

    def exit_app(self):
        self.poll_running = False
        self.running = False
        self.tray_running = False
        if self._auto_font_after_id:
            self.root.after_cancel(self._auto_font_after_id)
            self._auto_font_after_id = None
        self.remove_tray_icon()
        if self.tray_hwnd:
            try:
                win32gui.DestroyWindow(self.tray_hwnd)
            except:
                pass
        self.root.after(0, self.root.destroy)

    def on_closing(self):
        self.root.withdraw()


if __name__ == "__main__":
    App()
