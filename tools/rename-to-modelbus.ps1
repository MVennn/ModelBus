<#
  rename-to-modelbus.ps1 - one-shot project rename: ZcodeAIModels -> ModelBus

  Order (risky window kept short):
    1. preflight  2. stop gateways  3. rename dir  4. re-point junction
    5. re-register scheduled tasks  6. patch launchers outside the repo
    7. start gateway + /health  8. text replace in repo  9. git remote / commit / push

  Usage:
    powershell -NoProfile -ExecutionPolicy Bypass -File tools\rename-to-modelbus.ps1 -DryRun
    powershell -NoProfile -ExecutionPolicy Bypass -File tools\rename-to-modelbus.ps1

  -SkipGit : do not touch remote / commit / push
  -DryRun  : print the plan, change nothing
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipGit
)

$ErrorActionPreference = 'Stop'

$SrcDir   = 'F:\Project\ZcodeAIModels'
$DstDir   = 'F:\Project\ModelBus'
$LinkRoot = 'F:\Project\_merged\DeepseekHarness'
$OldToken = 'ZcodeAIModels'
$NewToken = 'ModelBus'
$LocalDir = Join-Path $env:LOCALAPPDATA 'ZCodeGateway'
$StateOld = Join-Path $env:LOCALAPPDATA $OldToken
$StateNew = Join-Path $env:LOCALAPPDATA $NewToken
$Exts = @('.md', '.py', '.ps1', '.vbs', '.cmd', '.json', '.go', '.yml', '.yaml', '.txt')

function Say([string]$m) { Write-Host $m }
function Act([string]$m) { if ($DryRun) { Write-Host "PLAN  $m" } else { Write-Host "DO    $m" } }
function Die([string]$m) { Write-Host "ABORT: $m"; exit 1 }

Say "== rename $OldToken -> $NewToken =="
if ($DryRun) { Say "MODE: dry-run, nothing will be changed" }

# ---------- 1. preflight ----------
if (-not (Test-Path -LiteralPath $SrcDir)) { Die "source missing: $SrcDir" }
if (Test-Path -LiteralPath $DstDir)       { Die "target already exists: $DstDir" }

$OldLink = Join-Path $LinkRoot $OldToken
$NewLink = Join-Path $LinkRoot $NewToken
if (Test-Path -LiteralPath $OldLink) { Say "junction present: $OldLink" } else { Say "junction absent: $OldLink" }

$procs = @(Get-Process -Name 'zgate', 'wb2api' -ErrorAction SilentlyContinue)
if ($procs) { Say ("gateways running: " + (($procs | ForEach-Object { $_.ProcessName + '#' + $_.Id }) -join ', ')) }
else { Say "gateways running: none" }

$taskList = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like ($OldToken + '*') })
if ($taskList) { Say ("tasks found: " + (($taskList | ForEach-Object { $_.TaskName }) -join ' | ')) }
else { Say "tasks found: none" }

if (-not $DryRun) {
    $dirty = & git -C $SrcDir status --porcelain 2>$null
    if ($LASTEXITCODE -ne 0) { Die "git status failed in $SrcDir" }
    if ($dirty) { Say "WARN: working tree not clean:"; $dirty | ForEach-Object { Say "      $_" } }
}

# leave the directory before it is renamed: a process whose CWD sits inside it
# blocks Move-Item on Windows.
Set-Location $env:TEMP

# ---------- 2. stop gateways ----------
# Disable the watchdog first: it fires every minute and would restart zgate.exe
# from inside the directory while we try to rename it -> ERROR_ACCESS_DENIED.
$Watchdog = Get-ScheduledTask -ErrorAction SilentlyContinue |
    Where-Object { $_.TaskName -like ($OldToken + '-zgate-watchdog') } | Select-Object -First 1
Act "disable watchdog task (it would restart zgate mid-rename)"
if (-not $DryRun -and $Watchdog) {
    Disable-ScheduledTask -TaskName $Watchdog.TaskName -TaskPath $Watchdog.TaskPath | Out-Null
}

Act "stop zgate.exe / wb2api.exe"
if (-not $DryRun) {
    Get-Process -Name 'zgate', 'wb2api' -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Milliseconds 1200
    $left = @(Get-Process -Name 'zgate', 'wb2api' -ErrorAction SilentlyContinue)
    if ($left) { Die ("still running: " + (($left | ForEach-Object { $_.Id }) -join ',')) }
}

# ---------- 3. rename directory ----------
Act "rename dir  $SrcDir -> $DstDir"
if (-not $DryRun) {
    # A renamed directory gets ERROR_ACCESS_DENIED while any process still maps a
    # binary inside it (zgate.exe / wb2api.exe) or sits in it as CWD. Retry while
    # killing stragglers instead of dying on the first attempt.
    $renamed = $false
    for ($attempt = 1; $attempt -le 40; $attempt++) {
        try {
            Move-Item -LiteralPath $SrcDir -Destination $DstDir -ErrorAction Stop
            $renamed = $true
            break
        } catch {
            $lastError = $_.Exception.Message
            Get-Process -Name 'zgate', 'wb2api' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $renamed) { Die ("rename still blocked after 40 attempts: " + $lastError + " - nothing else was changed") }
}
$Root = if ($DryRun) { $SrcDir } else { $DstDir }

# ---------- 4. junction ----------
if (Test-Path -LiteralPath $OldLink) {
    Act "remove junction $OldLink"
    if (-not $DryRun) { & cmd /c rmdir "$OldLink" | Out-Null }
}
Act "create junction $NewLink -> $DstDir"
if (-not $DryRun) {
    & cmd /c mklink /J "$NewLink" "$DstDir" | Out-Null
    if (-not (Test-Path -LiteralPath $NewLink)) { Die "junction creation failed" }
}

# ---------- 5. scheduled tasks ----------
foreach ($task in $taskList) {
    $taskNewName = $task.TaskName.Replace($OldToken, $NewToken)
    Act ("task  " + $task.TaskName + "  ->  " + $taskNewName)
    if ($DryRun) { continue }
    $xmlText = Export-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
    $xmlText = $xmlText.Replace($OldToken, $NewToken)
    Register-ScheduledTask -TaskName $taskNewName -TaskPath $task.TaskPath -Xml $xmlText -Force | Out-Null
    Unregister-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -Confirm:$false | Out-Null
}

# ---------- 6. launchers / configs / shortcuts outside the repo ----------
# Any text file that hardcodes the old path or the old token gets rewritten.
# ZcodeAIModels -> ModelBus keeps the drive/prefix, so token replacement alone
# already fixes every JSON-escaped form (F:\\Project\\ZcodeAIModels) too.
function PatchTextFile([string]$Path) {
    $enc = New-Object System.Text.UTF8Encoding($false)
    $text = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    $orig = $text
    $text = $text.Replace($SrcDir, $DstDir).Replace($OldToken, $NewToken)
    if ($text -eq $orig) { return $false }
    [System.IO.File]::WriteAllText($Path, $text, $enc)
    return $true
}

function PatchShortcut([string]$Path) {
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($Path)
    $changed = $false
    if ($lnk.TargetPath -and $lnk.TargetPath.Contains($OldToken)) {
        $lnk.TargetPath = $lnk.TargetPath.Replace($OldToken, $NewToken)
        $changed = $true
    }
    if ($lnk.WorkingDirectory -and $lnk.WorkingDirectory.Contains($OldToken)) {
        $lnk.WorkingDirectory = $lnk.WorkingDirectory.Replace($OldToken, $NewToken)
        $changed = $true
    }
    if ($changed) { $lnk.Save() }
    return $changed
}

$LauncherExts = @('.ps1', '.vbs', '.bat', '.cmd')
Act "patch launchers in $LocalDir (.ps1 .vbs .bat .cmd)"
if (-not $DryRun) {
    foreach ($file in (Get-ChildItem -LiteralPath $LocalDir -File -Force -ErrorAction SilentlyContinue)) {
        if ($LauncherExts -notcontains $file.Extension.ToLower()) { continue }
        if (PatchTextFile $file.FullName) { Say ("      patched " + $file.Name) }
    }
}

$ZcodeSetting = Join-Path $env:USERPROFILE '.zcode\v2\setting.json'
Act "patch $ZcodeSetting (workspacePath)"
if (-not $DryRun -and (Test-Path -LiteralPath $ZcodeSetting)) {
    if (PatchTextFile $ZcodeSetting) { Say "      patched setting.json" }
}

Act "patch $LinkRoot\AGENTS.md"
if (-not $DryRun) {
    $agentsMd = Join-Path $LinkRoot 'AGENTS.md'
    if (Test-Path -LiteralPath $agentsMd) {
        if (PatchTextFile $agentsMd) { Say "      patched AGENTS.md" }
    }
}

$ShortcutDirs = @(
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'),
    (Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned'),
    [Environment]::GetFolderPath('Desktop')
)
Act "repair shortcuts pointing at $OldToken (start menu / taskbar pins / desktop)"
if (-not $DryRun) {
    foreach ($dir in $ShortcutDirs) {
        if (-not (Test-Path -LiteralPath $dir)) { continue }
        foreach ($lnkFile in (Get-ChildItem -LiteralPath $dir -Filter '*.lnk' -File -Recurse -ErrorAction SilentlyContinue)) {
            if (PatchShortcut $lnkFile.FullName) { Say ("      retargeted " + $lnkFile.Name) }
            if ($lnkFile.Name.Contains($OldToken)) {
                $newName = $lnkFile.Name.Replace($OldToken, $NewToken)
                Rename-Item -LiteralPath $lnkFile.FullName -NewName $newName
                Say ("      renamed " + $lnkFile.Name + " -> " + $newName)
            }
        }
    }
}

Act "move state dir $StateOld -> $StateNew"
if (-not $DryRun -and (Test-Path -LiteralPath $StateOld) -and -not (Test-Path -LiteralPath $StateNew)) {
    Move-Item -LiteralPath $StateOld -Destination $StateNew
}

# ---------- 7. start gateway ----------
$Exe = Join-Path $Root 'gateways\zgate\zgate.exe'
$WorkDir = Join-Path $Root 'gateways\zgate'
Act "start $Exe serve"
if (-not $DryRun) {
    if (-not (Test-Path -LiteralPath $Exe)) { Die "gateway binary missing: $Exe" }
    Start-Process -FilePath $Exe -ArgumentList 'serve' -WorkingDirectory $WorkDir -WindowStyle Hidden
    $healthy = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $resp = Invoke-WebRequest 'http://127.0.0.1:7871/health' -TimeoutSec 2 -UseBasicParsing
            if ($resp.StatusCode -eq 200) { $healthy = $true; break }
        } catch { }
    }
    if (-not $healthy) {
        Say "HEALTH FAIL - rolling back"
        Get-Process -Name 'zgate', 'wb2api' -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Milliseconds 600
        Move-Item -LiteralPath $DstDir -Destination $SrcDir
        if (Test-Path -LiteralPath $NewLink) { & cmd /c rmdir "$NewLink" | Out-Null }
        & cmd /c mklink /J "$OldLink" "$SrcDir" | Out-Null
        Die "gateway did not come up; directory and junction restored (tasks already re-registered)"
    }
    Say "HEALTH OK"
    $watchdogNew = Get-ScheduledTask -ErrorAction SilentlyContinue |
        Where-Object { $_.TaskName -like ($NewToken + '-zgate-watchdog') } | Select-Object -First 1
    if ($watchdogNew -and $watchdogNew.State -ne 'Ready') {
        Enable-ScheduledTask -TaskName $watchdogNew.TaskName -TaskPath $watchdogNew.TaskPath | Out-Null
        Say "      watchdog re-enabled"
    }
}

# ---------- 8. text replace in repo ----------
Act "replace '$OldToken' -> '$NewToken' in text files"
if (-not $DryRun) {
    $files = Get-ChildItem -LiteralPath $Root -Recurse -File -Force |
        Where-Object { $Exts -contains $_.Extension.ToLower() -and $_.Name -ne 'rename-to-modelbus.ps1' -and $_.FullName -notmatch '\\\.git\\' -and $_.FullName -notmatch '\\node_modules\\' }
    $hits = 0
    foreach ($file in $files) {
        try { $body = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8) } catch { continue }
        if (-not $body.Contains($OldToken)) { continue }
        $body2 = $body.Replace($SrcDir, $DstDir).Replace($OldToken, $NewToken)
        [System.IO.File]::WriteAllText($file.FullName, $body2, (New-Object System.Text.UTF8Encoding($false)))
        $hits++
    }
    Say "      rewrote $hits files"
}

# ---------- 9. git ----------
if (-not $SkipGit) {
    Act "git remote set-url + commit + push + gh repo rename"
    if (-not $DryRun) {
        & git -C $Root remote set-url origin ("https://github.com/MVennn/" + $NewToken + ".git")
        & git -C $Root add -A
        & git -C $Root commit -m ("chore: rename project to " + $NewToken) -m ("Directory, junction, scheduled tasks, docs and launchers now use " + $NewToken + "; the gateway binary keeps its name.") | Out-Null
        $pushOut = & git -C $Root push origin main 2>&1
        Say ((($pushOut | Select-Object -Last 3)) -join [Environment]::NewLine).Trim()
        $ghOut = & gh repo rename $NewToken --repo ("MVennn/" + $OldToken) --yes 2>&1
        Say ((($ghOut)) -join [Environment]::NewLine).Trim()
    }
}

Say "== done =="
Say "path     : $DstDir"
Say "junction : $NewLink"