# M2Server 菜单自动化工具 — 开发总结报告

## 项目概述

实现对 M2Server.exe（996引擎传奇服务端）窗口菜单的自动化操作。通过全局热键 `Ctrl+S` 触发，自动定位目标窗口、识别菜单结构、按序执行指定子项。

## 技术栈

| 组件 | 用途 |
|------|------|
| `pywin32` | Windows API 封装（窗口枚举、热键注册、消息投递） |
| `pywinauto` | 菜单结构遍历与子项识别 |
| `psutil` | 进程名获取与验证 |
| `ctypes` | 低层 Windows API 调用（消息循环） |

## 开发历程

### 阶段一：窗口定位与进程验证

```
EnumWindows → GetWindowText(996引擎 + KUAFU) → 
GetWindowThreadProcessId → psutil.Process.name() == M2Server.exe
```

- 遍历所有顶层可见窗口
- 过滤标题同时包含 `"996引擎"` 和 `"KUAFU"` 的窗口
- 获取 PID 并验证进程名为 `M2Server.exe`

### 阶段二：菜单遍历

使用 `pywinauto` 的 `menu().items()` 遍历菜单栏，递归获取子菜单：

```
GetMenu → GetMenuItemCount → sub_menu() → items() → item.text()
```

成功获取菜单结构：

```
控制(&V) → 启动服务、关闭服务、清除日志、重新加载、游戏网关、退出程序
重新加载(&X) → 物品数据、怪物数据、重载爆率、重载套装、&Buff、LuaFunc函数库……
```

### 阶段三：菜单项执行

通过 `item.item_id()` 获取菜单项命令 ID，使用 `PostMessage(hwnd, WM_COMMAND, id, 0)` 直接触发，**不依赖鼠标模拟**。

### 阶段四：全局热键

**第一版 — 低层键盘钩子 (WH_KEYBOARD_LL)**
- 拦截所有按键事件，Python 回调处理每个键击
- 导致打字明显卡顿
- 已弃用

**第二版 — RegisterHotKey（最终方案）**
- Windows 内核级热键，仅在 `Ctrl+S` 按下时触发
- 不影响正常键盘输入，无延迟
- **真正全局**：在任何应用中按下 `Ctrl+S` 均有效

## 最终架构

```
┌─────────────────────────────────────────────────────┐
│                     main.py                          │
│                                                      │
│  RegisterHotKey(Ctrl+S)                              │
│       ↓                                              │
│  WM_HOTKEY → WndProc → PostMessage(WM_TRIGGER_TASK)  │
│       ↓                                              │
│  WM_TRIGGER_TASK → process_ctrl_s()                  │
│       ↓                                              │
│  ┌─ EnumWindows (查找 996引擎+KUAFU 窗口)           │
│  ├─ psutil (验证 M2Server.exe)                       │
│  ├─ pywinauto (遍历菜单 & 子菜单)                    │
│  └─ PostMessage WM_COMMAND (执行子项)                │
└─────────────────────────────────────────────────────┘
```

## 文件清单

| 文件 | 说明 |
|------|------|
| `main.py` | 主程序（最终版） |

## 运行说明

1. 确保依赖已安装：
   ```cmd
   pip install pywin32 pywinauto psutil
   ```
2. 运行：
   ```cmd
   python main.py
   ```
3. 在任意应用中按 `Ctrl+S` 触发
4. 按 `Ctrl+C` 退出程序

## 执行内容

在"控制(&V)"→"重新加载(&X)"中，按顺序执行 11 个子项：

1. 物品数据(&I)
2. 怪物数据(&K)
3. 重载爆率(&O)
4. 重载套装(&P)
5. &Buff Ctrl+B
6. LuaFunc函数库(&L) Ctrl+L
7. LuaCond条件函数库(&U) Ctrl+K
8. &QFunction Ctrl+F
9. Q&Manage Ctrl+M
10. 重载机器人(&Y)
11. 所有NPC(&N) Ctrl+N

## 注意事项

- 热键 `Ctrl+S` 可能被其他程序占用，此时程序会提示并仅执行一次初始任务
- 程序运行后保持后台消息循环，不会自动退出
- 执行菜单项通过 `SendMessage/PostMessage` 直接投递命令，不模拟鼠标点击
