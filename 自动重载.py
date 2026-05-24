import tkinter as tk
from tkinter import ttk
import threading
import time
import win32gui
import win32process
import win32con
import psutil
import pywinauto
from pywinauto.application import Application
import ctypes
from ctypes import wintypes
import sys

sys.stdout.reconfigure(line_buffering=True)

VK_CONTROL = 0x11
VK_S = 0x53


class App:
    def __init__(self):
        self.running = True
        self.m2_pid = None
        self.m2_hwnd = None
        self.check_vars = {}

        self.root = tk.Tk()
        self.root.title("M2Server 重载管理")
        self.root.geometry("480x520")
        self.root.resizable(False, True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.build_ui()
        self.load_data()
        self.start_polling()

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
        ttk.Button(btn_frame, text="刷新", command=self.refresh, width=8).pack(side="right", padx=2)

        container = ttk.Frame(self.root)
        container.pack(fill="both", expand=True, padx=10, pady=5)

        canvas = tk.Canvas(container, highlightthickness=0, bg="#f0f0f0")
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.items_frame = ttk.Frame(canvas)

        self.items_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.items_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.status_var = tk.StringVar(value="就绪，等待 Ctrl+S...")
        ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 10))

    def select_all(self):
        for v in self.check_vars.values():
            v.set(True)

    def deselect_all(self):
        for v in self.check_vars.values():
            v.set(False)

    def refresh(self):
        self.load_data()

    def load_data(self):
        for w in self.items_frame.winfo_children():
            w.destroy()
        self.check_vars.clear()

        self.status_var.set("正在获取菜单...")
        self.root.update()

        items = self._fetch_reload_items()

        default_prefixes = [
            "物品数据", "怪物数据(&K)", "重载爆率", "重载套装",
            "&Buff", "LuaFunc函数库", "LuaCond条件函数库",
            "&QFunction", "Q&Manage", "重载机器人", "所有NPC",
        ]

        for text in items:
            checked = any(text.startswith(p) or p in text for p in default_prefixes)
            var = tk.BooleanVar(value=checked)
            ttk.Checkbutton(self.items_frame, text=text, variable=var).pack(anchor="w", padx=5, pady=1)
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
        """轮询线程检测 Ctrl+S，不拦截任何按键"""
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

            # 检测上升沿：从"未按下"变为"按下"
            if now_pressed and not self.ctrl_s_was_pressed:
                now = time.time()
                if now - self._last_trigger >= 1.0:
                    self._last_trigger = now
                    self.root.after(0, self.execute_checked)

            self.ctrl_s_was_pressed = now_pressed
            time.sleep(0.05)

    def execute_checked(self):
        checked = [t for t, v in self.check_vars.items() if v.get()]
        if not checked:
            self.status_var.set("没有选中任何项目")
            return

        if not self.m2_hwnd:
            self.status_var.set("未连接到 M2Server，请刷新")
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

    def on_closing(self):
        self.poll_running = False
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    App()
