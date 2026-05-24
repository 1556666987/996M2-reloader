import win32gui, win32process, ctypes, time
from ctypes import wintypes

# 找窗口
hwnds = []
def enum_cb(hwnd, hwnds):
    if win32gui.IsWindowVisible(hwnd):
        t = win32gui.GetWindowText(hwnd)
        if t and "996引擎" in t and "KUAFU" in t:
            hwnds.append(hwnd)
    return True
win32gui.EnumWindows(enum_cb, hwnds)
main_hwnd = hwnds[0] if hwnds else exit()

target_memo = None
def find_memo(hwnd):
    global target_memo
    if win32gui.GetClassName(hwnd) == "TMemo":
        target_memo = hwnd; return False
    def cb(c, _): find_memo(c); return True
    win32gui.EnumChildWindows(hwnd, cb, None)
find_memo(main_hwnd)
if not target_memo: exit()

class LOGFONTW(ctypes.Structure):
    _fields_ = [("lfHeight", wintypes.LONG), ("lfWidth", wintypes.LONG),
        ("lfEscapement", wintypes.LONG), ("lfOrientation", wintypes.LONG),
        ("lfWeight", wintypes.LONG), ("lfItalic", wintypes.BYTE),
        ("lfUnderline", wintypes.BYTE), ("lfStrikeOut", wintypes.BYTE),
        ("lfCharSet", wintypes.BYTE), ("lfOutPrecision", wintypes.BYTE),
        ("lfClipPrecision", wintypes.BYTE), ("lfQuality", wintypes.BYTE),
        ("lfPitchAndFamily", wintypes.BYTE), ("lfFaceName", wintypes.WCHAR * 32)]

gdi32, user32 = ctypes.windll.gdi32, ctypes.windll.user32
gdi32.CreateFontIndirectW.argtypes = [ctypes.POINTER(LOGFONTW)]
gdi32.CreateFontIndirectW.restype = wintypes.HANDLE
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_long

lf = LOGFONTW()
lf.lfHeight = -24
lf.lfFaceName = "Consolas"
lf.lfCharSet = 134
hfont = gdi32.CreateFontIndirectW(ctypes.byref(lf))
user32.SendMessageW(target_memo, 0x0030, hfont, 1)
print(f"已应用 {lf.lfFaceName} 字体 (大小{-lf.lfHeight})")
