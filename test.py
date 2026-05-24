import win32gui
import win32process
import win32con
import psutil
import pywinauto
from pywinauto import Desktop
from pywinauto.application import Application
import ctypes
import time

# 目标：查找"日志信息"页签中的编辑器，内容包含"【老刀框架】初始化中"

# 第一步：找到M2Server窗口
hwnds = []
def enum_cb(hwnd, hwnds):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if title and "996引擎" in title and "KUAFU" in title:
            hwnds.append(hwnd)
    return True

win32gui.EnumWindows(enum_cb, hwnds)
if not hwnds:
    print("未找到目标窗口")
    exit()

hwnd = hwnds[0]
_, pid = win32process.GetWindowThreadProcessId(hwnd)
print(f"主窗口: hwnd={hwnd}, pid={pid}, title={win32gui.GetWindowText(hwnd)}")

# 第二步：递归枚举所有子窗口
def enum_child(hwnd, indent=0):
    prefix = "  " * indent
    title = win32gui.GetWindowText(hwnd)
    cls = win32gui.GetClassName(hwnd)
    
    # 如果能获取文本内容，也打印出来（限制长度）
    text_preview = ""
    try:
        if "Edit" in cls or "RichEdit" in cls or "TMemo" in cls or "EDIT" in cls:
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.SendMessageW(hwnd, 0x000D, 256, ctypes.byref(buf))  # WM_GETTEXT
            text_preview = f" content=[{buf.value[:80]}]"
    except:
        pass
    
    print(f"{prefix}hwnd={hwnd}, class={cls}, text='{title}'{text_preview}")
    
    def child_cb(child, _):
        enum_child(child, indent + 1)
        return True
    
    win32gui.EnumChildWindows(hwnd, child_cb, None)

print("\n===== 所有子窗口 =====")
enum_child(hwnd)

# 第三步：用pywinauto查找包含指定文本的控件
print("\n===== 用pywinauto查找 =====")
try:
    app = Application(backend="win32").connect(process=pid)
    dlg = app.window(title_re=".*996引擎.*KUAFU.*")
    
    # 查找"日志信息"页签
    print("\n--- 查找 '日志信息' 页签 ---")
    log_tab = dlg.child_window(title="日志信息")
    if log_tab.exists():
        print(f"找到日志信息页签: {log_tab}")
        log_tab.click()
        time.sleep(0.5)
    else:
        print("未找到日志信息页签，尝试其他方式...")
        # 尝试通过类名查找
        tabs = dlg.child_window(class_name="TTabSheet")
        print(f"TTabSheet控件: {tabs}")
    
    # 查找包含 "老刀框架" 的控件
    print("\n--- 查找包含【老刀框架】的控件 ---")
    try:
        target = dlg.child_window(title_re=".*老刀框架.*")
        if target.exists():
            print(f"找到: {target}")
            print(f"  class: {target.class_name()}")
            print(f"  text: {target.window_text()}")
        else:
            print("未通过标题找到，尝试查找编辑器控件...")
    except:
        pass
    
    # 枚举所有控件文本
    print("\n--- 枚举所有控件文本 ---")
    for ctrl in dlg.descendants():
        try:
            txt = ctrl.window_text()
            if txt and "老刀" in txt:
                print(f"  找到! class={ctrl.class_name()}, text={txt}")
        except:
            pass
    
except Exception as e:
    print(f"pywinauto错误: {e}")
    import traceback
    traceback.print_exc()
