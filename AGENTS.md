# 项目级协作约定

## GitHub 网络代理

访问 GitHub 远程仓库（`https://github.com/...`）时，必须通过本机代理 `127.0.0.1:7897`。

PowerShell 会话中可使用：

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:7897"
$env:HTTPS_PROXY = "http://127.0.0.1:7897"
```

执行 Git 命令时，也可以显式指定：

```powershell
git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 fetch origin
```

如果代理未启动或端口不可用，应明确报告网络连接失败，不要将其误判为远程仓库不存在。
