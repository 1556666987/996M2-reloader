# 项目级协作约定

## GitHub 网络代理

访问 GitHub 远程仓库（`https://github.com/...`）时，自动使用系统代理：检测到系统代理就走系统代理，没有系统代理则直连，不得因缺少代理而报告网络失败。

系统代理按以下顺序判定，取第一个命中的结果：

1. 环境变量 `HTTPS_PROXY`、`HTTP_PROXY`（已设置且非空时）；
2. 注册表 `HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings` 中 `ProxyEnable = 1` 时的 `ProxyServer`。

### 在 PowerShell 会话中应用

```powershell
$proxy = $env:HTTPS_PROXY
if (-not $proxy) { $proxy = $env:HTTP_PROXY }
if (-not $proxy) {
    $reg = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
    if ($reg.ProxyEnable -eq 1 -and $reg.ProxyServer) { $proxy = "http://$($reg.ProxyServer)" }
}

if ($proxy) {
    $env:HTTP_PROXY = $proxy
    $env:HTTPS_PROXY = $proxy
    Write-Host "使用系统代理: $proxy"
} else {
    Write-Host "未检测到系统代理，直连"
}
```

### 执行 Git 命令时

有系统代理则显式传入，没有则不加代理参数：

```powershell
$gitProxyArgs = @()
if ($proxy) { $gitProxyArgs = @("-c", "http.proxy=$proxy", "-c", "https.proxy=$proxy") }
git @gitProxyArgs push origin master
```

## 注意事项

- 本机代理端口可能变化（例如 `127.0.0.1:10808`），不要在任何脚本或约定里写死端口。
- 代理连接失败时才报告网络错误，并在报错里附上当时检测到的代理地址，便于区分“代理不可用”和“远程仓库不存在”。
