# 打包脚本：把 自动重载.pyw 打包成单文件 exe，输出到脚本同目录。
#
# 依赖环境（本机已验证可用）：
#   Python 3.14.3         C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe
#   PyInstaller 6.22.2
#   运行期依赖：tkinter、pywin32、psutil、pywinauto、pystray、Pillow（均为本机已安装的第三方包）
#
# 用法：在项目目录执行  powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
#
# 说明：
#   --onefile    打成单个 exe；启动时自解包到 %TEMP%\_MEIxxxx，属正常现象。
#                引导进程（小内存、不创建窗口）与应用子进程（真正界面与托盘）是两个进程。
#   --noconsole  不弹黑窗口（.pyw 的图形程序）。
#   --add-data   把 icon.ico 打进包内；源码用 sys._MEIPASS 读取托盘图标。
#                config.json 不打进包内，始终读写 exe 同目录，便于换机器后重新记录。
#   中间产物输出到临时目录，避免污染仓库。

$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$ScriptPath = Join-Path $ProjectDir "自动重载.pyw"
$IconPath   = Join-Path $ProjectDir "icon.ico"
$BuildDir   = Join-Path $env:TEMP "pyi_build_reloader"

if (-not (Test-Path $ScriptPath)) { throw "找不到脚本: $ScriptPath" }
if (-not (Test-Path $IconPath))   { throw "找不到图标: $IconPath" }

New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

python -m PyInstaller `
    --onefile `
    --noconsole `
    --name "自动重载" `
    --icon $IconPath `
    --add-data "$IconPath;." `
    --distpath $ProjectDir `
    --workpath (Join-Path $BuildDir "work") `
    --specpath $BuildDir `
    --noconfirm `
    --clean `
    $ScriptPath

if ($LASTEXITCODE -ne 0) { throw "打包失败，退出码 $LASTEXITCODE" }

$exe = Join-Path $ProjectDir "自动重载.exe"
$size = [math]::Round((Get-Item $exe).Length / 1MB, 2)
Write-Host "打包完成: $exe ($size MB)"
Write-Host "提示: 若程序正在运行，需先退出托盘的旧实例再启动新 exe。"
