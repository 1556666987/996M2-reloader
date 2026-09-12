# 工作计划：补发窗口尺寸消息

## 目标

在 `SetWindowPos` 调整 M2Server 与客户端控制台窗口后，向对应窗口补发一次 `WM_SIZE`，帮助目标程序刷新内部布局。

## 已确认信息

- 计划文件：`plan/work_plan.md`，完成后归档至 `plan/finish/`。
- 现有恢复逻辑使用 `SetWindowPos`，窗口位置和尺寸已可正确恢复。
- 补发消息使用 `WM_SIZE`、`SIZE_RESTORED` 和实际设置的宽高。

## 详细工作计划

- [x] 1. 在窗口恢复流程追加 `WM_SIZE` 消息。
- [x] 2. 执行现场窗口恢复、语法和差异检查。
- [x] 3. 将计划归档至 `plan/finish/`。

## 已经完成

- 已在每次 `SetWindowPos` 成功后调用 `SendMessage(hwnd, WM_SIZE, SIZE_RESTORED, MAKELONG(width, height))`。
- 已验证两个目标窗口最终矩形保持默认布局。
- `python -m py_compile 自动重载.pyw` 和 `git diff --check` 通过。

## 待确认问题 / 阻塞项

- 暂无。

## 下一步

计划已完成，准备归档。

## 验收标准

- 两个目标窗口均执行 `SetWindowPos` 后补发 `WM_SIZE`。
- 窗口最终位置和尺寸正确。
- 代码通过语法检查。

## 更新记录

- [2026-09-12 01:00] 完成 `WM_SIZE` 补发及现场验证。
