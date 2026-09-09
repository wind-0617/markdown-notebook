#Requires -Version 5.0
<#
  run.ps1 —— Windows 一键启动脚本（配合 优化文档/启动脚本.txt·方案二）
  自动完成：检测 Python → 建虚拟环境（失败自动回退 backend\.deps）→ 装依赖
            → 启动 Flask → 等待就绪 → 打开浏览器 → 挂起至 Ctrl+C

  用法：
    .\run.ps1               一键启动
    .\run.ps1 -Reinstall    强制重装依赖
    .\run.ps1 -NoBrowser    不自动开浏览器（调试/CI）
    .\run.ps1 -Stop         停止由本脚本启动的服务
  首次执行若被策略拦截：
    powershell -ExecutionPolicy Bypass -File .\run.ps1
#>
[CmdletBinding()]
param(
    [switch]$Reinstall,
    [switch]$NoBrowser,
    [switch]$Stop
)

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
Set-Location $PSScriptRoot
Write-Host "📁 当前目录: $(Get-Location)"

$bindHost = if ($env:HOST) { $env:HOST } else { '127.0.0.1' }
$port     = if ($env:PORT) { $env:PORT } else { '5000' }
$url      = "http://${bindHost}:${port}"

function Test-Server {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "$url/api/health" -TimeoutSec 2 -ErrorAction Stop
        return $r.StatusCode -eq 200
    } catch { return $false }
}

# ---------- 停止模式 ----------
if ($Stop) {
    Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'app\.py' } |
        ForEach-Object {
            Write-Host "🛑 停止服务进程 PID=$($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    exit 0
}

# ---------- 1. 定位 Python ----------
$py = 'python', 'python3', 'py' | ForEach-Object { Get-Command $_ -ErrorAction SilentlyContinue } |
      Select-Object -First 1
if (-not $py) {
    Write-Host "❌ 未找到 Python（需 3.10+），请安装后加入 PATH。" -ForegroundColor Red
    exit 1
}
Write-Host "🐍 Python: $($py.Source)"

# ---------- 0. 已在运行？直接体验 ----------
if (Test-Server) {
    Write-Host "♻️  服务已在运行：$url" -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $url }
    exit 0
}

# ---------- 2. 虚拟环境（失败回退 backend\.deps） ----------
$pyRun  = $py.Source
$venvPy = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Host "🔧 创建虚拟环境 venv/ ..."
    try { & $pyRun -m venv (Join-Path $PSScriptRoot 'venv') 2>$null | Out-Null } catch { }
}
$useVenv = Test-Path $venvPy
if (-not $useVenv) {
    if (Test-Path (Join-Path $PSScriptRoot 'venv')) {
        Remove-Item (Join-Path $PSScriptRoot 'venv') -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "⚠️  venv 不可用，回退方案：系统 Python + backend\.deps（app.py 自动识别）" -ForegroundColor Yellow
} else {
    $pyRun = $venvPy
}

# ---------- 3. 安装依赖（marker 防重复） ----------
$req = Join-Path $PSScriptRoot 'backend\requirements.txt'
if ($useVenv) {
    $marker = Join-Path $PSScriptRoot 'venv\.deps-ok'
    if ($Reinstall -or -not (Test-Path $marker)) {
        Write-Host "📦 安装依赖到 venv ..."
        & $pyRun -m pip install --disable-pip-version-check -q -r $req
        if ($LASTEXITCODE -eq 0) { New-Item -ItemType File -Path $marker -Force | Out-Null }
    } else {
        Write-Host "📦 依赖已就绪（如需重装：.\run.ps1 -Reinstall）"
    }
} elseif ($Reinstall -or -not (Test-Path (Join-Path $PSScriptRoot 'backend\.deps'))) {
    Write-Host "📦 安装依赖到 backend\.deps ..."
    & $pyRun -m pip install --disable-pip-version-check -q --no-cache-dir --target backend\.deps -r $req
} else {
    Write-Host "📦 backend\.deps 已存在，跳过安装"
}

# ---------- 4. 启动后端 ----------
if (-not $env:FLASK_DEBUG) { $env:FLASK_DEBUG = '0' }   # 单进程模式，Ctrl+C 可干净终止
$env:HOST = $bindHost
$env:PORT = $port
Write-Host "🚀 启动后端服务（$url）..."
$proc = Start-Process -FilePath $pyRun -ArgumentList 'app.py' `
        -WorkingDirectory (Join-Path $PSScriptRoot 'backend') `
        -PassThru -WindowStyle Hidden
Write-Host "   服务 PID = $($proc.Id)"

# ---------- 5. 轮询就绪（最多 15s）→ 开浏览器 ----------
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-Server) { $ready = $true; break }
    if ($proc.HasExited) { break }
}
if ($ready) {
    Write-Host "✅ 服务就绪：$url" -ForegroundColor Green
    if (-not $NoBrowser) {
        Write-Host "🌐 打开浏览器 ..."
        Start-Process $url
    }
} elseif ($proc.HasExited) {
    Write-Host "❌ 服务启动失败（进程退出）。端口可能被占用，排查：" -ForegroundColor Red
    Write-Host "   netstat -ano | findstr :$port"
    exit 1
} else {
    Write-Host "⏳ 就绪探测超时，服务可能仍在启动，请稍后手动访问 $url" -ForegroundColor Yellow
}

# ---------- 6. 挂起等待，Ctrl+C 连带停止服务 ----------
Write-Host "✔ 完成。关闭此窗口或按 Ctrl+C 可用 `.\run.ps1 -Stop` 停止服务。"
try {
    while (-not $proc.HasExited) { Start-Sleep -Milliseconds 500 }
} catch {
    # Ctrl+C
} finally {
    if (-not $proc.HasExited) {
        Write-Host "🛑 正在停止服务 PID=$($proc.Id) ..."
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}
