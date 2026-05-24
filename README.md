# 996M2 Reloader

用于 996 引擎 M2Server 的重新加载辅助工具。程序会自动识别 M2Server 窗口中的“控制 -> 重新加载”菜单项，并通过快捷键批量执行选中的重载项目。

## 功能特性

- 自动查找标题包含 `996引擎` 和 `KUAFU` 的 M2Server 窗口
- 验证目标进程为 `M2Server.exe`
- 自动读取“控制 -> 重新加载”菜单下的子项
- 支持勾选需要执行的重载项目
- 按 `Ctrl+S` 批量执行已勾选项目
- 支持全选、取消全选、刷新菜单
- 支持修改 M2Server 日志窗口字体和字号
- 自动保存字体配置和勾选项到 `config.json`
- 启动后默认隐藏到系统托盘
- 关闭窗口时最小化到托盘，托盘菜单支持显示和退出

## 运行环境

- Windows
- Python 3.x
- 目标程序：996 引擎 `M2Server.exe`

## 依赖安装

```powershell
pip install pywin32 pywinauto psutil pystray pillow
```

## 使用方法

1. 启动 996 引擎的 `M2Server.exe`。
2. 运行本工具：

   ```powershell
   python 自动重载.pyw
   ```

3. 程序启动后默认进入系统托盘。
4. 双击托盘图标或右键选择“显示”打开主界面。
5. 点击“刷新”读取 M2Server 的重新加载菜单。
6. 勾选需要自动执行的重载项。
7. 在任意窗口按 `Ctrl+S`，程序会按顺序执行已勾选的重载项。

## 配置文件

程序会在同目录下读写：

```text
config.json
```

当前保存内容包括：

- `font_name`：日志窗口字体
- `font_size`：日志窗口字号
- `selected_items`：已勾选的重载菜单项

示例：

```json
{
  "font_name": "Segoe UI",
  "font_size": 22,
  "selected_items": [
    "&QFunction\tCtrl+F"
  ]
}
```

## 默认重载项目

首次运行且没有保存配置时，程序会默认勾选以下类型的项目：

- 物品数据
- 怪物数据
- 重载爆率
- 重载套装
- Buff
- LuaFunc 函数库
- LuaCond 条件函数库
- QFunction
- QManage
- 重载机器人
- 所有 NPC

实际显示内容以 M2Server 菜单为准。

## 版本

当前稳定版本：

```text
v1.0.1.0
```

版本号规则采用：

```text
主版本.次版本.修订版本.构建版本
```

标签格式：

```text
v主版本.次版本.修订版本.构建版本
```

递增规则：

- 主版本：发生不兼容的重大变化时递增。
- 次版本：新增功能且保持兼容时递增。
- 修订版本：修复 Bug、优化稳定性时递增。
- 构建版本：文档、配置、资源文件、打包或内部维护变更时递增。

完整更新记录见：

```text
CHANGELOG.md
```

查看本地标签：

```powershell
git tag
```

回滚到当前稳定版本：

```powershell
git reset --hard v1.0.1.0
git push --force-with-lease
```

## 注意事项

- 本工具仅适用于 Windows。
- 需要先启动 M2Server，否则会提示未找到目标窗口。
- 目标窗口标题需要包含 `996引擎` 和 `KUAFU`。
- 如果 M2Server 重启过，建议点击“刷新”重新连接。
- `Ctrl+S` 会作为全局触发键使用，注意避免和其他工具流程冲突。
- 托盘图标默认读取项目目录内的 `icon.ico`，读取失败时会使用内置纯色图标。

## 仓库地址

```text
https://github.com/1556666987/996M2-reloader
```
