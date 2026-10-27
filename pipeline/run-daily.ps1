# TOEFL daily pipeline runner (called by Windows Task Scheduler)
# NOTE: keep this file ASCII-only. PowerShell 5.1 reads .ps1 as ANSI when no BOM,
# so non-ASCII text here gets corrupted and causes parse errors.
# Logs go to pipeline\logs, falling back to %TEMP%\toefl-logs.
$ErrorActionPreference = "Continue"
$AppDir     = "E:\2026\toefl-app"
$Py         = "E:\ai\comfyui\ComfyUI_windows_portable\python_embeded\python.exe"
$StatusFile = Join-Path $AppDir "pipeline\last-run.json"

function Resolve-LogDir {
  $primary = Join-Path $AppDir "pipeline\logs"
  try {
    New-Item -ItemType Directory -Force -Path $primary -ErrorAction Stop | Out-Null
    if (Test-Path $primary) { return $primary }
  } catch {}
  $fallback = Join-Path $env:TEMP "toefl-logs"
  New-Item -ItemType Directory -Force -Path $fallback | Out-Null
  return $fallback
}

$LogDir = Resolve-LogDir
$Log    = Join-Path $LogDir ("run-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")

function Log($msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  $line | Tee-Object -FilePath $Log -Append | Out-Null
  Write-Output $line
}

function Save-Status($obj) {
  try { $obj | ConvertTo-Json -Depth 4 | Set-Content -Path $StatusFile -Encoding UTF8 } catch {}
}

$started = Get-Date
$result  = @{ started = $started.ToString("s"); logDir = $LogDir; ok = $false; stage = "init"; error = $null }

try {
  Log "=== START ==="
  Log ("PowerShell {0} | user {1} | cwd {2}" -f $PSVersionTable.PSVersion, $env:USERNAME, (Get-Location))
  Log ("Python exists: " + (Test-Path $Py) + " -> " + $Py)

  if (-not (Test-Path $Py)) { throw "python not found: $Py" }

  $result.stage = "ollama"
  if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) {
    Log "ollama not running, starting"
    $exe = "E:\ai\ollama\ollama.exe"
    if (Test-Path $exe) { Start-Process $exe -ArgumentList "serve" -WindowStyle Hidden }
    Start-Sleep -Seconds 8
  }
  $ollamaOk = $false
  try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10 -UseBasicParsing
    $ollamaOk = ($resp.StatusCode -eq 200)
  } catch {}
  Log ("ollama reachable: " + $ollamaOk)

  $result.stage = "pipeline"
  Set-Location (Join-Path $AppDir "pipeline")
  & $Py "run_daily.py" *>> $Log
  $pyExit = $LASTEXITCODE
  $result.pyExit = $pyExit
  Log ("pipeline exit code: " + $pyExit)
  if ($pyExit -ne 0) { throw "pipeline failed with exit code $pyExit" }
  $result.stage = "notify"
  $notifyScript = Join-Path $AppDir "pipeline\notify_qq.py"
  if (Test-Path $notifyScript) {
    & $Py $notifyScript *>> $Log
    Log ("qq notify exit code: " + $LASTEXITCODE)
  }


  $result.stage = "git"
  Set-Location $AppDir
  if (Test-Path ".git") {
    git add -A 2>&1 | Out-Null
    $changes = git status --porcelain
    if ($changes) {
      git -c user.name="hinawihako" -c user.email="hinawithako@gmail.com" commit -m ("daily: " + (Get-Date -Format "yyyy-MM-dd")) 2>&1 | Out-Null
      $push = git push 2>&1
      $push | Out-File -FilePath $Log -Append
      if ($LASTEXITCODE -eq 0) { Log "pushed, Pages will rebuild" } else { throw "git push failed: $push" }
    } else {
      Log "no changes, skip commit"
    }
  } else {
    Log "not a git repo, skip push"
  }

  $result.ok = $true
  $result.stage = "done"
  Log "=== DONE (ok) ==="
}
catch {
  $result.error = $_.Exception.Message
  Log ("!!! FAILED at stage [" + $result.stage + "]: " + $_.Exception.Message)
  Log ("stack: " + $_.ScriptStackTrace)
  exit 1
}
finally {
  $result.durationSec = [int]((Get-Date) - $started).TotalSeconds
  Save-Status $result
}

