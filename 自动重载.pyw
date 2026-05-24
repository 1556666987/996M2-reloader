import tkinter as tk
from tkinter import ttk
import threading
import time
import json
import os
import win32gui
import win32process
import win32con
import psutil
import pywinauto
from pywinauto.application import Application
import pystray
from PIL import Image
import ctypes
from ctypes import wintypes

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
TRAY_ICON_PATH = r"D:\源码\1.ico"
VK_CONTROL = 0x11
VK_S = 0x53
WM_TRAYICON = win32con.WM_USER + 20
TRAY_UID = 1
ID_TRAY_SHOW = 1000
ID_TRAY_EXIT = 1001
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
    except:
        pass

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

        self.root = tk.Tk()
        self.root.title("M2Server 重载管理")
        self.root.geometry("480x580")
        self.root.resizable(False, True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.withdraw()  # 启动后默认只显示托盘图标

        self.build_ui()
        self.load_data()
        self.start_polling()
        self.start_tray_icon()

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

        # 查找TMemo
        target_memo = None
        def find_memo(hwnd):
            nonlocal target_memo
            if win32gui.GetClassName(hwnd) == "TMemo":
                target_memo = hwnd
                return False
            def cb(c, _):
                find_memo(c)
                return True
            win32gui.EnumChildWindows(hwnd, cb, None)

        find_memo(self.m2_hwnd)
        if not target_memo:
            self.status_var.set("未找到日志编辑器(TMemo)")
            return

        # 创建字体并应用
        gdi32 = ctypes.windll.gdi32
        user32 = ctypes.windll.user32
        gdi32.CreateFontIndirectW.argtypes = [ctypes.POINTER(LOGFONTW)]
        gdi32.CreateFontIndirectW.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.SendMessageW.restype = ctypes.c_long
        user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
        user32.InvalidateRect.restype = wintypes.BOOL

        lf = LOGFONTW()
        lf.lfHeight = -font_size
        lf.lfCharSet = 134
        lf.lfFaceName = font_name
        hfont = gdi32.CreateFontIndirectW(ctypes.byref(lf))
        if hfont:
            user32.SendMessageW(target_memo, 0x0030, hfont, 1)
            user32.InvalidateRect(target_memo, None, True)
            save_config({"font_name": font_name, "font_size": font_size})
            self.cfg_font, self.cfg_size = font_name, str(font_size)
            self.status_var.set(f"字体已更新: {font_name} {font_size}")
        else:
            self.status_var.set("创建字体失败")

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
        hwnds = []

        def enum_cb(hwnd, hwnds):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and "996引擎" in title and "KUAFU" in title:
                    hwnds.append(hwnd)
            return True

        win32gui.EnumWindows(enum_cb, hwnds)
        if not hwnds:
            return []

        self.m2_hwnd = hwnds[0]
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
                    self.root.after(0, self.execute_checked)

            self.ctrl_s_was_pressed = now_pressed
            time.sleep(0.05)

    def _refresh_connection(self):
        hwnds = []
        def enum_cb(hwnd, hwnds):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and "996引擎" in title and "KUAFU" in title:
                    hwnds.append(hwnd)
            return True
        win32gui.EnumWindows(enum_cb, hwnds)
        if not hwnds:
            return False
        self.m2_hwnd = hwnds[0]
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
