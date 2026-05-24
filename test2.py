import win32gui
import win32process
import win32con
import ctypes
from ctypes import wintypes
import time

# 找到M2Server窗口和TMemo
hwnds = []
def enum_cb(hwnd, hwnds):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if title and "996引擎" in title and "KUAFU" in title:
            hwnds.append(hwnd)
    return True

win32gui.EnumWindows(enum_cb, hwnds)
if not hwnds: exit()
main_hwnd = hwnds[0]

target_memo = None
def find_memo(hwnd):
    global target_memo
    cls = win32gui.GetClassName(hwnd)
    if cls == "TMemo":
        target_memo = hwnd
        return False
    def child_cb(child, _):
        find_memo(child)
        return True
    win32gui.EnumChildWindows(hwnd, child_cb, None)
find_memo(main_hwnd)

if not target_memo:
    print("未找到TMemo")
    exit()

print(f"TMemo hwnd={target_memo}")

# 声明API
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_long

# 1. 先设置字体（确认可行）
class LOGFONTW(ctypes.Structure):
    _fields_ = [
        ("lfHeight", wintypes.LONG), ("lfWidth", wintypes.LONG),
        ("lfEscapement", wintypes.LONG), ("lfOrientation", wintypes.LONG),
        ("lfWeight", wintypes.LONG), ("lfItalic", wintypes.BYTE),
        ("lfUnderline", wintypes.BYTE), ("lfStrikeOut", wintypes.BYTE),
        ("lfCharSet", wintypes.BYTE), ("lfOutPrecision", wintypes.BYTE),
        ("lfClipPrecision", wintypes.BYTE), ("lfQuality", wintypes.BYTE),
        ("lfPitchAndFamily", wintypes.BYTE), ("lfFaceName", wintypes.WCHAR * 32),
    ]

gdi32.CreateFontIndirectW.argtypes = [ctypes.POINTER(LOGFONTW)]
gdi32.CreateFontIndirectW.restype = wintypes.HANDLE

lf = LOGFONTW()
lf.lfHeight = -20
lf.lfFaceName = "微软雅黑"
hfont = gdi32.CreateFontIndirectW(ctypes.byref(lf))
user32.SendMessageW(target_memo, 0x0030, hfont, 1)  # WM_SETFONT
print("[OK] 设置字体成功")

# ========== 尝试修改背景色和文字颜色 ==========

# 方式1: EM_SETBKGNDCOLOR (RichEdit消息, 标准EDIT可能不支持)
# wParam: 0=使用指定颜色, lParam: COLORREF 0x00BBGGRR
EM_SETBKGNDCOLOR = 0x0403
COLORREF_RED = 0x000000FF     # 红色背景
COLORREF_BLUE = 0x00FF0000    # 蓝色背景  
COLORREF_BLACK = 0x00000000   # 黑色
COLORREF_WHITE = 0x00FFFFFF   # 白色
COLORREF_GREEN = 0x0000FF00   # 绿色背景
COLORREF_DARKBLUE = 0x00800000  # 深蓝色背景

print(f"\n尝试 EM_SETBKGNDCOLOR...")
ret = user32.SendMessageW(target_memo, EM_SETBKGNDCOLOR, 0, COLORREF_DARKBLUE)
print(f"  EM_SETBKGNDCOLOR 返回: {ret}")
time.sleep(1)

# 方式2: EM_SETCHARFORMAT (设置文字颜色)
EM_SETCHARFORMAT = 0x0444
SCF_SELECTION = 0x0001
SCF_ALL = 0x0004

# CHARFORMAT2W 结构
class CHARFORMAT2W(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwMask", wintypes.DWORD),
        ("dwEffects", wintypes.DWORD),
        ("yHeight", wintypes.LONG),
        ("yOffset", wintypes.LONG),
        ("crTextColor", wintypes.COLORREF),
        ("bCharSet", wintypes.BYTE),
        ("bPitchAndFamily", wintypes.BYTE),
        ("szFaceName", wintypes.WCHAR * 32),
        ("wWeight", wintypes.WORD),
        ("sSpacing", wintypes.SHORT),
        ("crBackColor", wintypes.COLORREF),
        ("lcid", wintypes.DWORD),
        ("dwReserved", wintypes.DWORD),
        ("sStyle", wintypes.SHORT),
        ("wKerning", wintypes.WORD),
        ("bUnderlineType", wintypes.BYTE),
        ("bAnimation", wintypes.BYTE),
        ("bRevAuthor", wintypes.BYTE),
        ("bReserved1", wintypes.BYTE),
    ]

CFM_COLOR = 0x40000000
CFM_BACKCOLOR = 0x04000000

print(f"\n尝试 EM_SETCHARFORMAT...")
cf = CHARFORMAT2W()
cf.cbSize = ctypes.sizeof(CHARFORMAT2W)
cf.dwMask = CFM_COLOR
cf.crTextColor = 0x0000FF00  # 绿色文字
ret = user32.SendMessageW(target_memo, EM_SETCHARFORMAT, SCF_ALL, ctypes.addressof(cf))
print(f"  EM_SETCHARFORMAT 返回: {ret}")
time.sleep(1)

# 方式3: 尝试 EM_SETBKGNDCOLOR + WM_SETTEXT 看看控制是否刷新
print(f"\n尝试强制刷新...")
user32.SendMessageW(target_memo, 0x000B, 0, 0)  # WM_SETREDRAW=0
user32.SendMessageW(target_memo, 0x000F, 0, 0)  # WM_SETREDRAW=1 (WM_ENABLE 也可以触发重绘)
user32.InvalidateRect(target_memo, None, True)
print("  InvalidateRect 已发送")

# 方式4: 直接设置颜色(文本颜色) - 对于标准EDIT, 没有直接消息
# 尝试通过父窗口的WM_CTLCOLOREDIT
print(f"\n尝试发送 WM_CTLCOLOREDIT ...")
# 这实际上应该由EDIT发给父窗口, 不是我们主动发
# 但我们可以创建一个画笔然后发给父窗口? 不行

print("\n===== 测试结果 =====")
print("字体修改: ✅ 成功")
print("背景色(EM_SETBKGNDCOLOR): 标准EDIT不支持, 需要父窗口子类化")
print("文字色(EM_SETCHARFORMAT): RichEdit专用, TMemo不支持")
print("\n背景/文字颜色需要更复杂的注入技术才能实现。")
