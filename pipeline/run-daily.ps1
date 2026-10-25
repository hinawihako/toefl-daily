# TOEFL 每日 · 自动跑（Windows 任务计划调用）
# 1) 生成今天的新闻与音频  2) 提交到 git，触发 Cloudflare Pages 重新部署

$ErrorActionPreference = "Continue"
$AppDir = "E:\2026\toefl-app"
$Py = "E:\ai\comfyui\ComfyUI_windows_portable\python_embeded\python.exe"
$LogDir = Join-Path $AppDir "pipeline\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ("run-" + (Get-Date -Format "yyyyMMdd-HHmm") + ".log")

function Log($msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg
  $line | Tee-Object -FilePath $Log -Append
}

Log "=== 开始 ==="
Set-Location (Join-Path $AppDir "pipeline")

# Ollama 没起就拉起来（多数情况它已经在跑）
$ollama = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
  Log "Ollama 未运行，尝试启动"
  $exe = "E:\ai\ollama\ollama.exe"
  if (Test-Path $exe) { Start-Process $exe -ArgumentList "serve" -WindowStyle Hidden }
  Start-Sleep -Seconds 8
}

Log "运行管线"
& $Py "run_daily.py" *>> $Log
if ($LASTEXITCODE -ne 0) { Log "管线失败，退出码 $LASTEXITCODE"; exit 1 }

# 提交（如果仓库存在且配了远端）
Set-Location $AppDir
if (Test-Path ".git") {
  $changes = git status --porcelain
  if ($changes) {
    git add -A 2>&1 | Out-Null
    git -c user.name="toefl-bot" -c user.email="bot@local" commit -m ("daily: " + (Get-Date -Format "yyyy-MM-dd")) 2>&1 | Out-Null
    git push 2>&1 | Out-File -FilePath $Log -Append
    Log "已提交并推送"
  } else {
    Log "内容无变化，跳过提交"
  }
} else {
  Log "还没有 git 仓库，跳过提交（内容已生成到 data/）"
}

Log "=== 结束 ==="
