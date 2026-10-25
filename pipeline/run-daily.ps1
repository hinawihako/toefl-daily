# TOEFL 每日 · 自动跑（Windows 任务计划调用）
# 1) 生成今天的新闻与音频  2) 提交并推送 → GitHub Pages 自动重建
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

# Ollama 没起就拉起来
if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) {
  Log "Ollama 未运行，尝试启动"
  $exe = "E:\ai\ollama\ollama.exe"
  if (Test-Path $exe) { Start-Process $exe -ArgumentList "serve" -WindowStyle Hidden }
  Start-Sleep -Seconds 8
}

Log "运行管线"
& $Py "run_daily.py" *>> $Log
if ($LASTEXITCODE -ne 0) { Log "管线失败，退出码 $LASTEXITCODE" }

# 提交并推送
Set-Location $AppDir
if (Test-Path ".git") {
  git add -A 2>&1 | Out-Null
  $changes = git status --porcelain
  if ($changes) {
    git -c user.name="hinawihako" -c user.email="hinawithako@gmail.com" `
        commit -m ("daily: " + (Get-Date -Format "yyyy-MM-dd")) 2>&1 | Out-Null
    $push = git push 2>&1
    $push | Out-File -FilePath $Log -Append
    if ($LASTEXITCODE -eq 0) { Log "已推送，Pages 会自动重建" } else { Log "推送失败：$push" }
  } else {
    Log "内容无变化，跳过提交"
  }
} else {
  Log "没有 git 仓库，跳过推送"
}
Log "=== 结束 ==="
